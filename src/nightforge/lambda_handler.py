from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

from nightforge.webhook import verify_github_signature


_MAX_PAYLOAD_BYTES = 1_048_576
_ALLOWED_EVENTS = frozenset({"check_suite", "ping"})


def _response(status_code: int, document: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(document, ensure_ascii=False),
    }


def _headers(event: dict[str, Any]) -> dict[str, str]:
    source = event.get("headers") or {}
    normalized = {str(key).lower(): str(value) for key, value in source.items()}
    return {
        "X-GitHub-Delivery": normalized.get("x-github-delivery", ""),
        "X-GitHub-Event": normalized.get("x-github-event", ""),
        "X-Hub-Signature-256": normalized.get("x-hub-signature-256", ""),
    }


def _payload(event: dict[str, Any]) -> bytes:
    body = event.get("body") or ""
    if not isinstance(body, str):
        raise ValueError("webhook body must be a string")
    try:
        return base64.b64decode(body, validate=True) if event.get("isBase64Encoded") else body.encode("utf-8")
    except ValueError as error:
        raise ValueError("invalid base64 webhook body") from error


def create_lambda_handler(secret: str, repository: str, delivery_table: Any) -> Callable[[dict[str, Any], Any], dict[str, Any]]:
    def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
        request = event.get("requestContext", {}).get("http", {})
        if request.get("method") != "POST" or request.get("path") != "/webhook":
            return _response(404, {"error": "not found"})
        try:
            payload = _payload(event)
            if len(payload) > _MAX_PAYLOAD_BYTES:
                raise ValueError("webhook payload is too large")
            headers = _headers(event)
            delivery_id = headers["X-GitHub-Delivery"]
            webhook_event = headers["X-GitHub-Event"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", delivery_id):
                raise ValueError("invalid GitHub delivery ID")
            if webhook_event not in _ALLOWED_EVENTS:
                raise ValueError(f"unsupported webhook event: {webhook_event}")
            verify_github_signature(payload, headers["X-Hub-Signature-256"], secret)
            receipt = {
                "delivery_id": delivery_id,
                "event": webhook_event,
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                delivery_table.put_item(Item=receipt, ConditionExpression="attribute_not_exists(delivery_id)")
            except delivery_table.exceptions.ConditionalCheckFailedException:
                return _response(200, {"accepted": False, "delivery_id": delivery_id, "duplicate": True})
            if webhook_event == "ping":
                return _response(202, {"accepted": True, **receipt})
            # The receipt has already been atomically claimed in DynamoDB.  The local
            # receipt directory is unused for Lambda events, so process the state transition directly.
            document = json.loads(payload)
            from nightforge.webhook import process_check_suite_event

            transition = process_check_suite_event(repository, document)
            return _response(202, {"accepted": True, **receipt, "transition": transition})
        except (ValueError, json.JSONDecodeError) as error:
            return _response(400, {"error": str(error)})

    return handler


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    secret = os.environ.get("NIGHTFORGE_WEBHOOK_SECRET")
    repository = os.environ.get("NIGHTFORGE_GITHUB_REPOSITORY")
    table_name = os.environ.get("NIGHTFORGE_DELIVERY_TABLE")
    if not secret or not repository or not table_name:
        return _response(500, {"error": "missing required NightForge Lambda configuration"})
    import boto3

    return create_lambda_handler(secret, repository, boto3.resource("dynamodb").Table(table_name))(event, context)
