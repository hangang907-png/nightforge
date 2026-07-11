import json
from pathlib import Path

import pytest

from nightforge.github import (
    build_claim_update,
    build_draft_pull_request,
    build_state_update,
    require_opt_in,
)


def test_claim_update_replaces_open_state_and_preserves_labels():
    issue = {
        "number": 7,
        "labels": [{"name": "kind:ticket"}, {"name": "state:open"}, {"name": "documentation"}],
        "assignees": [],
    }

    update = build_claim_update(issue, "hangang907-png")

    assert update == {
        "assignees": ["hangang907-png"],
        "labels": ["kind:ticket", "documentation", "state:claimed"],
    }


def test_claim_update_rejects_non_ticket_issue():
    issue = {"number": 8, "labels": [{"name": "state:open"}], "assignees": []}

    with pytest.raises(ValueError, match="not a NightForge ticket"):
        build_claim_update(issue, "node-a")


def test_claim_update_rejects_already_claimed_ticket():
    issue = {
        "number": 9,
        "labels": [{"name": "kind:ticket"}, {"name": "state:claimed"}],
        "assignees": [{"login": "node-a"}],
    }

    with pytest.raises(ValueError, match="not open"):
        build_claim_update(issue, "node-b")


def test_registry_rejects_repository_without_maintainer_opt_in(tmp_path):
    registry = tmp_path / "repositories.json"
    registry.write_text(json.dumps({"schema_version": "0.1", "repositories": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="not opted in"):
        require_opt_in("owner/repo", registry)


def test_draft_pull_request_payload_cannot_be_published_ready():
    payload = build_draft_pull_request("nightforge/ticket-1", "main", "Repair CI", "Closes #1")

    assert payload["draft"] is True
    assert payload["head"] == "nightforge/ticket-1"


def test_state_update_preserves_non_state_labels():
    issue = {
        "labels": [
            {"name": "kind:ticket"},
            {"name": "state:claimed"},
            {"name": "documentation"},
        ]
    }

    assert build_state_update(issue, "state:submitted") == {
        "labels": ["kind:ticket", "documentation", "state:submitted"]
    }


def test_state_update_rejects_invalid_transition():
    issue = {"labels": [{"name": "kind:ticket"}, {"name": "state:claimed"}]}

    with pytest.raises(ValueError, match="invalid ticket transition"):
        build_state_update(issue, "state:accepted")
