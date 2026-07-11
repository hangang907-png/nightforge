import pytest

from nightforge.webhook import pull_request_transition_from_event, ticket_issue_from_pull_request


def test_check_suite_start_moves_ticket_to_verifying():
    payload = {"action": "requested", "check_suite": {"pull_requests": [{"number": 12}]}}

    assert pull_request_transition_from_event("check_suite", payload) == (12, "state:verifying")


def test_successful_check_suite_accepts_ticket():
    payload = {
        "action": "completed",
        "check_suite": {"conclusion": "success", "pull_requests": [{"number": 12}]},
    }

    assert pull_request_transition_from_event("check_suite", payload) == (12, "state:accepted")


def test_failed_check_suite_rejects_ticket():
    payload = {
        "action": "completed",
        "check_suite": {"conclusion": "failure", "pull_requests": [{"number": 12}]},
    }

    assert pull_request_transition_from_event("check_suite", payload) == (12, "state:rejected")


def test_pull_request_body_links_ticket_issue():
    assert ticket_issue_from_pull_request({"body": "Ticket Issue: #42"}) == 42


def test_pull_request_without_ticket_link_is_rejected():
    with pytest.raises(ValueError, match="ticket issue"):
        ticket_issue_from_pull_request({"body": "No link"})
