import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from nightforge.cli import claim_ticket, record_webhook_delivery, submit_result, validate_document


ROOT = Path(__file__).parents[1]


def valid_ticket():
    return {
        "schema_version": "0.1",
        "id": "DEV-1",
        "rfc_id": "RFC-1",
        "title": "Repair failing CI workflow",
        "repository": "owner/repo",
        "base_ref": "main",
        "task_type": "ci-repair",
        "acceptance": ["all tests pass"],
        "budget": {"agent_minutes": 30, "max_cost_usd": 1.5},
        "deadline": "2026-07-12T00:00:00Z",
    }


def test_validate_ticket_accepts_valid_document():
    validate_document(valid_ticket(), ROOT / "schemas/ticket.schema.json")


def test_claim_creates_node_bound_receipt(tmp_path):
    ticket_path = tmp_path / "ticket.json"
    ticket_path.write_text(json.dumps(valid_ticket()), encoding="utf-8")

    receipt = claim_ticket(ticket_path, "node-a", tmp_path / "claims")

    assert receipt["ticket_id"] == "DEV-1"
    assert receipt["node_id"] == "node-a"
    assert receipt["ticket_sha256"] == hashlib.sha256(ticket_path.read_bytes()).hexdigest()
    assert (tmp_path / "claims/DEV-1.node-a.json").exists()


def test_claim_rejects_invalid_ticket(tmp_path):
    ticket = valid_ticket()
    ticket["repository"] = "not-a-repository"
    ticket_path = tmp_path / "ticket.json"
    ticket_path.write_text(json.dumps(ticket), encoding="utf-8")

    with pytest.raises(ValueError, match="repository"):
        claim_ticket(ticket_path, "node-a", tmp_path / "claims")


def test_submit_result_hashes_patch_and_records_tests(tmp_path):
    patch = tmp_path / "change.patch"
    patch.write_text("diff --git a/a b/a\n", encoding="utf-8")

    manifest = submit_result("DEV-1", "node-a", patch, ["pytest -q"], tmp_path / "submissions")

    assert manifest["artifact_sha256"] == hashlib.sha256(patch.read_bytes()).hexdigest()
    assert manifest["verification_commands"] == ["pytest -q"]
    assert (tmp_path / "submissions/DEV-1.node-a.json").exists()


def test_webhook_delivery_is_recorded_only_once(tmp_path):
    payload = b'{"action":"opened"}'

    first = record_webhook_delivery("delivery-123", "issues", payload, tmp_path / "deliveries")
    duplicate = record_webhook_delivery("delivery-123", "issues", payload, tmp_path / "deliveries")

    assert first["accepted"] is True
    assert duplicate == {"accepted": False, "delivery_id": "delivery-123", "duplicate": True}
    receipt = json.loads((tmp_path / "deliveries/delivery-123.json").read_text(encoding="utf-8"))
    assert receipt["event"] == "issues"
    assert receipt["payload_sha256"] == hashlib.sha256(payload).hexdigest()


def test_webhook_delivery_rejects_unsafe_id(tmp_path):
    with pytest.raises(ValueError, match="delivery ID"):
        record_webhook_delivery("../escape", "issues", b"{}", tmp_path / "deliveries")


def test_webhook_cli_records_payload(tmp_path):
    payload = tmp_path / "payload.json"
    payload.write_bytes(b'{"action":"opened"}')
    output = tmp_path / "deliveries"

    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/nightforge"),
            "webhook",
            "delivery-456",
            "issues",
            str(payload),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["accepted"] is True
    assert (output / "delivery-456.json").exists()
