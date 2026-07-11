import hashlib
import hmac

import pytest

from nightforge.webhook import (
    accept_webhook,
    pull_request_transition_from_event,
    ticket_issue_from_pull_request,
    verify_github_signature,
)


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


def test_github_signature_accepts_exact_payload():
    payload = b'{"action":"completed"}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()

    verify_github_signature(payload, signature, "secret")


def test_github_signature_rejects_modified_payload():
    signature = "sha256=" + hmac.new(b"secret", b"original", hashlib.sha256).hexdigest()

    with pytest.raises(ValueError, match="signature"):
        verify_github_signature(b"modified", signature, "secret")


def test_secure_webhook_is_idempotent(tmp_path):
    payload = b'{"action":"requested"}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    headers = {
        "X-GitHub-Delivery": "delivery-1",
        "X-GitHub-Event": "check_suite",
        "X-Hub-Signature-256": signature,
    }

    first = accept_webhook(headers, payload, "secret", tmp_path)
    duplicate = accept_webhook(headers, payload, "secret", tmp_path)

    assert first["accepted"] is True
    assert duplicate["duplicate"] is True


def test_secure_webhook_rejects_oversized_payload(tmp_path):
    payload = b"x" * 11
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    headers = {
        "X-GitHub-Delivery": "delivery-2",
        "X-GitHub-Event": "check_suite",
        "X-Hub-Signature-256": signature,
    }

    with pytest.raises(ValueError, match="too large"):
        accept_webhook(headers, payload, "secret", tmp_path, max_payload_bytes=10)
