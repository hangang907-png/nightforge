from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nightforge.github import get_github_pull_request, transition_github_ticket


_TICKET_LINK = re.compile(r"Ticket Issue:\s*#([1-9][0-9]*)", re.IGNORECASE)
_DELIVERY_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_ALLOWED_EVENTS = frozenset({"check_suite", "ping"})


def verify_github_signature(payload: bytes, signature: str, secret: str) -> None:
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if not signature.startswith("sha256=") or not hmac.compare_digest(expected, signature):
        raise ValueError("invalid GitHub webhook signature")


def accept_webhook(
    headers: dict[str, str],
    payload: bytes,
    secret: str,
    delivery_dir: Path,
    max_payload_bytes: int = 1_048_576,
) -> dict[str, Any]:
    if len(payload) > max_payload_bytes:
        raise ValueError("webhook payload is too large")
    delivery_id = headers.get("X-GitHub-Delivery", "")
    event = headers.get("X-GitHub-Event", "")
    signature = headers.get("X-Hub-Signature-256", "")
    if not _DELIVERY_ID.fullmatch(delivery_id):
        raise ValueError("invalid GitHub delivery ID")
    if event not in _ALLOWED_EVENTS:
        raise ValueError(f"unsupported webhook event: {event}")
    verify_github_signature(payload, signature, secret)
    delivery_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = delivery_dir / f"{delivery_id}.json"
    receipt = {
        "accepted": True,
        "delivery_id": delivery_id,
        "event": event,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with receipt_path.open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError:
        return {"accepted": False, "delivery_id": delivery_id, "duplicate": True}
    return receipt


def handle_webhook(
    repository: str,
    headers: dict[str, str],
    payload: bytes,
    secret: str,
    delivery_dir: Path,
    max_payload_bytes: int = 1_048_576,
) -> dict[str, Any]:
    receipt = accept_webhook(headers, payload, secret, delivery_dir, max_payload_bytes)
    if receipt.get("duplicate") or receipt["event"] == "ping":
        return receipt
    document = json.loads(payload)
    result = process_check_suite_event(repository, document)
    return {**receipt, "transition": result}


def ticket_issue_from_pull_request(pull_request: dict[str, Any]) -> int:
    match = _TICKET_LINK.search(pull_request.get("body") or "")
    if not match:
        raise ValueError("pull request does not link a ticket issue")
    return int(match.group(1))


def pull_request_transition_from_event(event: str, payload: dict[str, Any]) -> tuple[int, str]:
    if event != "check_suite":
        raise ValueError(f"unsupported webhook event: {event}")
    suite = payload.get("check_suite", {})
    pull_requests = suite.get("pull_requests", [])
    if len(pull_requests) != 1:
        raise ValueError("check suite must reference exactly one pull request")
    action = payload.get("action")
    if action in {"requested", "rerequested"}:
        target = "state:verifying"
    elif action == "completed":
        target = "state:accepted" if suite.get("conclusion") == "success" else "state:rejected"
    else:
        raise ValueError(f"unsupported check_suite action: {action}")
    return int(pull_requests[0]["number"]), target


def process_check_suite_event(repository: str, payload: dict[str, Any]) -> dict[str, Any]:
    pull_number, target = pull_request_transition_from_event("check_suite", payload)
    pull_request = get_github_pull_request(repository, pull_number)
    issue_number = ticket_issue_from_pull_request(pull_request)
    issue = transition_github_ticket(repository, issue_number, target)
    return {"pull_request": pull_number, "ticket_issue": issue_number, "target": target, "issue": issue}
