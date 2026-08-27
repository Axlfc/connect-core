import os
import subprocess
import tempfile
import shutil
import pytest
from pathlib import Path

from worker_app.worktree import (
    GitWorktreeManager,
    validate_repo_url_or_path,
    validate_git_ref,
    validate_identifier,
)

# ---------------------------------------------------------------------------
# Validation Unit Tests
# ---------------------------------------------------------------------------

def test_validate_repo_url_or_path_valid():
    assert validate_repo_url_or_path("/path/to/repo") == "/path/to/repo"
    assert validate_repo_url_or_path("https://github.com/org/repo.git") == "https://github.com/org/repo.git"
    assert validate_repo_url_or_path("ssh://git@github.com/org/repo.git") == "ssh://git@github.com/org/repo.git"
    assert validate_repo_url_or_path("git@github.com:org/repo.git") == "git@github.com:org/repo.git"

def test_validate_repo_url_or_path_malicious_flag():
    with pytest.raises(ValueError, match="cannot start with '-'"):
        validate_repo_url_or_path("-u/upload-pack=touch /tmp/pwned")

    with pytest.raises(ValueError, match="cannot start with '-'"):
        validate_repo_url_or_path("--upload-pack=/bin/sh")

def test_validate_repo_url_or_path_malicious_scheme():
    with pytest.raises(ValueError, match="Forbidden or untrusted Git protocol scheme"):
        validate_repo_url_or_path("ext::sh -c touch /tmp/pwned")

    with pytest.raises(ValueError, match="Forbidden or untrusted Git protocol scheme"):
        validate_repo_url_or_path("fd::1")

    with pytest.raises(ValueError, match="Forbidden or untrusted Git URL scheme"):
        validate_repo_url_or_path("file:///etc/passwd")

def test_validate_repo_url_or_path_null_byte():
    with pytest.raises(ValueError, match="Null bytes are not allowed"):
        validate_repo_url_or_path("/path/to/repo\x00malicious")

def test_validate_git_ref_valid():
    assert validate_git_ref("main") == "main"
    assert validate_git_ref("HEAD") == "HEAD"
    assert validate_git_ref("cognito/task-123-attempt-01") == "cognito/task-123-attempt-01"
    assert validate_git_ref("feature/v1.0.0") == "feature/v1.0.0"

def test_validate_git_ref_malicious_flag():
    with pytest.raises(ValueError, match="cannot start with '-'"):
        validate_git_ref("--upload-pack=touch /tmp/pwned")

    with pytest.raises(ValueError, match="cannot start with '-'"):
        validate_git_ref("-o/tmp/pwned")

def test_validate_git_ref_invalid_chars():
    with pytest.raises(ValueError, match="contains invalid git ref characters"):
        validate_git_ref("feature/..")

    with pytest.raises(ValueError, match="contains whitespace"):
        validate_git_ref("branch with space")

    with pytest.raises(ValueError, match="Null bytes are not allowed"):
        validate_git_ref("main\x00evil")

def test_validate_identifier_valid():
    assert validate_identifier("repo-123") == "repo-123"
    assert validate_identifier("task_456") == "task_456"
    assert validate_identifier("v1.0.0") == "v1.0.0"

def test_validate_identifier_malicious_flag():
    with pytest.raises(ValueError, match="cannot start with '-'"):
        validate_identifier("--upload-pack=/tmp/pwned")

    with pytest.raises(ValueError, match="cannot start with '-'"):
        validate_identifier("-exec")

def test_validate_identifier_disallowed_chars():
    with pytest.raises(ValueError, match="contains disallowed characters"):
        validate_identifier("repo/id")

    with pytest.raises(ValueError, match="contains disallowed characters"):
        validate_identifier("repo; touch /tmp/pwned")


# ---------------------------------------------------------------------------
# Integration Tests with Real Temporary Git Repository
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_git_repo():
    temp_dir = tempfile.mkdtemp(prefix="cognito_test_repo_")
    repo_path = Path(temp_dir).resolve()

    # Init git repo and set committer identity
    subprocess.run(["git", "init"], cwd=repo_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

    # Initial commit
    test_file = repo_path / "README.md"
    test_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

    yield str(repo_path)

    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def worktree_manager(tmp_path):
    return GitWorktreeManager(base_worktree_dir=tmp_path / "worktrees")


def test_worktree_manager_normal_lifecycle(temp_git_repo, worktree_manager):
    # Validate repository
    head_commit = worktree_manager.validate_git_repo(temp_git_repo)
    assert len(head_commit) == 40  # SHA-1 hash

    assert not worktree_manager.is_dirty(temp_git_repo)

    # Create worktree
    wt_path, branch_name = worktree_manager.create_worktree(
        base_repo_path=temp_git_repo,
        repo_id="repo123",
        task_id="task456",
        attempt=1
    )

    assert os.path.exists(wt_path)
    assert branch_name == "cognito/task-task456-attempt-01"

    # Modify file in worktree and check diff
    wt_file = Path(wt_path) / "README.md"
    wt_file.write_text("# Modified Test Repo\n")

    diff = worktree_manager.get_diff(wt_path, head_commit)
    assert "Modified Test Repo" in diff

    # Cleanup worktree with force=True
    worktree_manager.cleanup_worktree(temp_git_repo, wt_path, force=True)
    assert not os.path.exists(wt_path)


def test_worktree_manager_rejects_malicious_inputs(temp_git_repo, worktree_manager):
    # Malicious repo path
    with pytest.raises(ValueError, match="cannot start with '-'"):
        worktree_manager.validate_git_repo("-u/upload-pack")

    # Malicious scheme repo path
    with pytest.raises(ValueError, match="Forbidden or untrusted Git protocol scheme"):
        worktree_manager.validate_git_repo("ext::sh -c evil")

    # Malicious repo_id
    with pytest.raises(ValueError, match="cannot start with '-'"):
        worktree_manager.create_worktree(temp_git_repo, repo_id="--flag", task_id="task1", attempt=1)

    # Malicious task_id
    with pytest.raises(ValueError, match="cannot start with '-'"):
        worktree_manager.create_worktree(temp_git_repo, repo_id="repo1", task_id="-o/tmp/pwned", attempt=1)

    # Malicious base_commit
    with pytest.raises(ValueError, match="cannot start with '-'"):
        worktree_manager.get_diff(temp_git_repo, base_commit="--output=/tmp/pwned")
