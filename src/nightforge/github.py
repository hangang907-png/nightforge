from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from nightforge.governance import transition_ticket_state


_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _label_names(issue: dict[str, Any]) -> list[str]:
    return [label["name"] if isinstance(label, dict) else label for label in issue.get("labels", [])]


def build_claim_update(issue: dict[str, Any], node: str) -> dict[str, list[str]]:
    labels = _label_names(issue)
    if "kind:ticket" not in labels:
        raise ValueError("issue is not a NightForge ticket")
    if "state:open" not in labels:
        raise ValueError("NightForge ticket is not open")
    transition_ticket_state("state:open", "state:claimed")
    retained = [label for label in labels if not label.startswith("state:")]
    assignees = [entry["login"] if isinstance(entry, dict) else entry for entry in issue.get("assignees", [])]
    return {
        "assignees": list(dict.fromkeys([*assignees, node])),
        "labels": [*retained, "state:claimed"],
    }


def _check_repository(repository: str) -> None:
    if not _REPOSITORY.fullmatch(repository):
        raise ValueError("repository must use owner/name format")


def _gh_api(endpoint: str, method: str = "GET", fields: dict[str, Any] | None = None) -> Any:
    command = ["gh", "api", endpoint, "--method", method]
    if fields is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(
        command,
        input=json.dumps(fields) if fields is not None else None,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "GitHub API request failed")
    return json.loads(result.stdout)


def list_open_tickets(repository: str) -> list[dict[str, Any]]:
    _check_repository(repository)
    issues = _gh_api(f"repos/{repository}/issues?state=open&labels=kind%3Aticket%2Cstate%3Aopen&per_page=100")
    return [issue for issue in issues if "pull_request" not in issue]


def claim_github_ticket(repository: str, issue_number: int, node: str) -> dict[str, Any]:
    _check_repository(repository)
    if issue_number < 1:
        raise ValueError("issue number must be positive")
    issue = _gh_api(f"repos/{repository}/issues/{issue_number}")
    update = build_claim_update(issue, node)
    return _gh_api(f"repos/{repository}/issues/{issue_number}", method="PATCH", fields=update)
