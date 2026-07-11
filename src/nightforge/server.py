from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable
from wsgiref.simple_server import make_server

from nightforge.webhook import handle_webhook


StartResponse = Callable[[str, list[tuple[str, str]]], Any]


def create_wsgi_app(secret: str, repository: str, delivery_dir: Path):
    def application(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        if environ.get("REQUEST_METHOD") != "POST" or environ.get("PATH_INFO") != "/webhook":
            start_response("404 Not Found", [("Content-Type", "application/json")])
            return [b'{"error":"not found"}']
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if length > 1_048_576:
                raise ValueError("webhook payload is too large")
            payload = environ["wsgi.input"].read(length)
            headers = {
                "X-GitHub-Delivery": environ.get("HTTP_X_GITHUB_DELIVERY", ""),
                "X-GitHub-Event": environ.get("HTTP_X_GITHUB_EVENT", ""),
                "X-Hub-Signature-256": environ.get("HTTP_X_HUB_SIGNATURE_256", ""),
            }
            result = handle_webhook(repository, headers, payload, secret, delivery_dir)
            status = "200 OK" if result.get("duplicate") else "202 Accepted"
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        except (ValueError, json.JSONDecodeError) as error:
            status = "400 Bad Request"
            body = json.dumps({"error": str(error)}).encode("utf-8")
        start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    return application


def run_server(secret: str, repository: str, delivery_dir: Path, host: str, port: int) -> None:
    application = create_wsgi_app(secret, repository, delivery_dir)
    with make_server(host, port, application) as server:
        server.serve_forever()
