from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


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


if __name__ == "__main__":
    main()
