import hashlib
import json
from pathlib import Path

import pytest

from nightforge.cli import claim_ticket, submit_result, validate_document


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
