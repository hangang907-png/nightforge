from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from nightforge.github import claim_github_ticket, create_draft_pull_request, list_open_tickets
from nightforge.governance import transition_ticket_state
from nightforge.publish import publish_manifest
from nightforge.server import run_server
from nightforge.webhook import process_check_suite_event


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_document(document: dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "$"
        raise ValueError(f"{location}: {error.message}")


def claim_ticket(ticket_path: Path, node_id: str, output_dir: Path) -> dict[str, Any]:
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    schema_path = Path(__file__).parents[2] / "schemas" / "ticket.schema.json"
    validate_document(ticket, schema_path)
    receipt = {
        "schema_version": "0.1",
        "ticket_id": ticket["id"],
        "node_id": node_id,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
        "ticket_sha256": _sha256(ticket_path),
    }
    _write_json(output_dir / f"{ticket['id']}.{node_id}.json", receipt)
    return receipt


def record_webhook_delivery(
    delivery_id: str,
    event: str,
    payload: bytes,
    output_dir: Path,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", delivery_id):
        raise ValueError("delivery ID must contain only letters, digits, underscores, or hyphens")
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / f"{delivery_id}.json"
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


def submit_result(
    ticket_id: str,
    node_id: str,
    patch_path: Path,
    verification_commands: list[str],
    output_dir: Path,
) -> dict[str, Any]:
    if not patch_path.is_file():
        raise ValueError(f"patch not found: {patch_path}")
    if not verification_commands:
        raise ValueError("at least one verification command is required")
    manifest = {
        "schema_version": "0.1",
        "ticket_id": ticket_id,
        "node_id": node_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "artifact": str(patch_path),
        "artifact_sha256": _sha256(patch_path),
        "verification_commands": verification_commands,
    }
    _write_json(output_dir / f"{ticket_id}.{node_id}.json", manifest)
    return manifest


def _print(document: dict[str, Any]) -> None:
    print(json.dumps(document, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="nightforge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("document", type=Path)
    validate_parser.add_argument("schema", type=Path)

    claim_parser = subparsers.add_parser("claim")
    claim_parser.add_argument("ticket", type=Path)
    claim_parser.add_argument("--node", required=True)
    claim_parser.add_argument("--output", type=Path, default=Path(".nightforge/claims"))

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("ticket_id")
    submit_parser.add_argument("patch", type=Path)
    submit_parser.add_argument("--node", required=True)
    submit_parser.add_argument("--verify", action="append", required=True)
    submit_parser.add_argument("--output", type=Path, default=Path(".nightforge/submissions"))

    webhook_parser = subparsers.add_parser("webhook")
    webhook_parser.add_argument("delivery_id")
    webhook_parser.add_argument("event")
    webhook_parser.add_argument("payload", type=Path)
    webhook_parser.add_argument("--output", type=Path, default=Path(".nightforge/deliveries"))

    transition_parser = subparsers.add_parser("transition")
    transition_parser.add_argument("current")
    transition_parser.add_argument("target")

    github_list_parser = subparsers.add_parser("github-list")
    github_list_parser.add_argument("repository")

    github_claim_parser = subparsers.add_parser("github-claim")
    github_claim_parser.add_argument("repository")
    github_claim_parser.add_argument("issue", type=int)
    github_claim_parser.add_argument("--node", required=True)

    draft_parser = subparsers.add_parser("github-draft")
    draft_parser.add_argument("repository")
    draft_parser.add_argument("head")
    draft_parser.add_argument("--base", default="main")
    draft_parser.add_argument("--title", required=True)
    draft_parser.add_argument("--body", required=True)
    draft_parser.add_argument("--registry", type=Path, default=Path("config/repositories.json"))

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("manifest", type=Path)
    publish_parser.add_argument("--repo-path", type=Path, default=Path("."))
    publish_parser.add_argument("--github-repo", required=True)
    publish_parser.add_argument("--base", default="main")
    publish_parser.add_argument("--issue", type=int)
    publish_parser.add_argument("--registry", type=Path, default=Path("config/repositories.json"))

    webhook_state_parser = subparsers.add_parser("webhook-state")
    webhook_state_parser.add_argument("repository")
    webhook_state_parser.add_argument("payload", type=Path)

    serve_parser = subparsers.add_parser("webhook-serve")
    serve_parser.add_argument("repository")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.add_argument("--secret-env", default="NIGHTFORGE_WEBHOOK_SECRET")
    serve_parser.add_argument("--deliveries", type=Path, default=Path(".nightforge/deliveries"))

    args = parser.parse_args()
    if args.command == "validate":
        document = json.loads(args.document.read_text(encoding="utf-8"))
        validate_document(document, args.schema)
        _print({"valid": True, "document": str(args.document)})
    elif args.command == "claim":
        _print(claim_ticket(args.ticket, args.node, args.output))
    elif args.command == "submit":
        _print(submit_result(args.ticket_id, args.node, args.patch, args.verify, args.output))
    elif args.command == "webhook":
        _print(record_webhook_delivery(args.delivery_id, args.event, args.payload.read_bytes(), args.output))
    elif args.command == "transition":
        target = transition_ticket_state(args.current, args.target)
        _print({"from": args.current, "to": target, "valid": True})
    elif args.command == "github-list":
        print(json.dumps(list_open_tickets(args.repository), ensure_ascii=False, indent=2))
    elif args.command == "github-claim":
        _print(claim_github_ticket(args.repository, args.issue, args.node))
    elif args.command == "github-draft":
        _print(
            create_draft_pull_request(
                args.repository, args.registry, args.head, args.base, args.title, args.body
            )
        )
    elif args.command == "publish":
        _print(
            publish_manifest(
                args.repo_path,
                args.manifest,
                args.github_repo,
                args.registry,
                args.base,
                args.issue,
            )
        )
    elif args.command == "webhook-state":
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        _print(process_check_suite_event(args.repository, payload))
    elif args.command == "webhook-serve":
        secret = os.environ.get(args.secret_env)
        if not secret:
            raise ValueError(f"missing webhook secret environment variable: {args.secret_env}")
        run_server(secret, args.repository, args.deliveries, args.host, args.port)


if __name__ == "__main__":
    main()
