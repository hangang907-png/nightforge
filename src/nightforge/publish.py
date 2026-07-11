from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from nightforge.github import create_draft_pull_request, require_opt_in


def _run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"command failed: {command[0]}")
    return result.stdout.strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("ticket and node IDs must contain letters or digits")
    return slug


def prepare_patch_branch(
    repository_path: Path,
    patch_path: Path,
    ticket_id: str,
    node_id: str,
    base_ref: str,
    verification_commands: list[str],
    worktree_root: Path,
) -> dict[str, Any]:
    if not patch_path.is_file():
        raise ValueError(f"patch not found: {patch_path}")
    if not verification_commands:
        raise ValueError("at least one verification command is required")
    branch = f"nightforge/{_slug(ticket_id)}-{_slug(node_id)}"
    worktree = worktree_root / branch.replace("/", "-")
    worktree_root.mkdir(parents=True, exist_ok=True)
    _run(["git", "worktree", "add", "-b", branch, str(worktree), base_ref], repository_path)
    try:
        _run(["git", "apply", "--check", str(patch_path.resolve())], worktree)
        _run(["git", "apply", str(patch_path.resolve())], worktree)
        for command in verification_commands:
            _run(["bash", "-lc", command], worktree)
        _run(["git", "add", "-A"], worktree)
        _run(["git", "commit", "-m", f"feat: apply {ticket_id} from {node_id}"], worktree)
        commit_sha = _run(["git", "rev-parse", "HEAD"], worktree)
    except Exception:
        _run(["git", "worktree", "remove", "--force", str(worktree)], repository_path)
        subprocess.run(["git", "branch", "-D", branch], cwd=repository_path, capture_output=True)
        raise
    _run(["git", "worktree", "remove", str(worktree)], repository_path)
    return {"branch": branch, "commit_sha": commit_sha, "verification_commands": verification_commands}


def publish_manifest(
    repository_path: Path,
    manifest_path: Path,
    github_repository: str,
    registry_path: Path,
    base_ref: str,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = Path(manifest["artifact"])
    if not artifact.is_absolute():
        artifact = manifest_path.parent / artifact
    if not artifact.is_file():
        raise ValueError(f"patch not found: {artifact}")
    actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if actual_hash != manifest.get("artifact_sha256"):
        raise ValueError("patch SHA-256 does not match submission manifest")
    require_opt_in(github_repository, registry_path)
    prepared = prepare_patch_branch(
        repository_path,
        artifact,
        manifest["ticket_id"],
        manifest["node_id"],
        base_ref,
        manifest["verification_commands"],
        repository_path / ".git" / "nightforge-worktrees",
    )
    _run(["git", "push", "-u", "origin", prepared["branch"]], repository_path)
    pull_request = create_draft_pull_request(
        github_repository,
        registry_path,
        prepared["branch"],
        base_ref,
        f"{manifest['ticket_id']}: NightForge submission from {manifest['node_id']}",
        f"NightForge automated Draft PR.\n\nTicket: {manifest['ticket_id']}\nPatch SHA-256: `{actual_hash}`",
    )
    return {**prepared, "pull_request": pull_request, "artifact_sha256": actual_hash}
