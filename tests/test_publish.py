import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from nightforge.publish import prepare_patch_branch, publish_manifest


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


def test_prepare_patch_branch_applies_patch_and_runs_verification(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "NightForge Test")
    git(repo, "config", "user.email", "nightforge@example.test")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    patch = tmp_path / "change.patch"
    patch.write_text(
        "diff --git a/result.txt b/result.txt\nnew file mode 100644\n--- /dev/null\n+++ b/result.txt\n@@ -0,0 +1 @@\n+published\n",
        encoding="utf-8",
    )

    result = prepare_patch_branch(
        repo,
        patch,
        ticket_id="DEV-7",
        node_id="node-a",
        base_ref="main",
        verification_commands=["test -f result.txt"],
        worktree_root=tmp_path / "worktrees",
    )

    assert result["branch"] == "nightforge/dev-7-node-a"
    assert git(repo, "show", f"{result['branch']}:result.txt") == "published"
    assert len(result["commit_sha"]) == 40


def test_publish_manifest_rejects_modified_patch(tmp_path):
    patch = tmp_path / "change.patch"
    patch.write_text("original", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "ticket_id": "DEV-7",
                "node_id": "node-a",
                "artifact": str(patch),
                "artifact_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
                "verification_commands": ["true"],
            }
        ),
        encoding="utf-8",
    )
    patch.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        publish_manifest(tmp_path, manifest, "owner/repo", tmp_path / "registry.json", "main")
