import pytest

from nightforge.github import build_claim_update


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
