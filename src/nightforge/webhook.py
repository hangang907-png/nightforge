from __future__ import annotations

import re
from typing import Any

from nightforge.github import get_github_pull_request, transition_github_ticket


_TICKET_LINK = re.compile(r"Ticket Issue:\s*#([1-9][0-9]*)", re.IGNORECASE)


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
