from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path
from typing import List

import pytest

import executor as exctr


@pytest.fixture()
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary git repo with one notebook."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    (tmp_path / "nb").mkdir()
    nb_file: Path = tmp_path / "nb" / "test.ipynb"
    nb_file.write_text(
        json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5})
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_notebook_to_py_path(fake_repo: Path) -> None:
    nb: Path = fake_repo / "nb" / "test.ipynb"
    dst: Path = exctr._notebook_to_py_path(notebook_path=nb, repo_root=fake_repo, output_dir="artifacts/gha-nbconvert")
    assert dst == fake_repo / "artifacts/gha-nbconvert" / "nb" / "test.py"


def test_path_traversal(fake_repo: Path) -> None:
    bad: Path = fake_repo / ".." / "evil.ipynb"
    with pytest.raises(exctr.PathTraversalError):
        exctr._notebook_to_py_path(notebook_path=bad, repo_root=fake_repo, output_dir="artifacts/gha-nbconvert")


def test_convert_notebook(fake_repo: Path) -> None:
    nb: Path = fake_repo / "nb" / "test.ipynb"
    dst: Path = exctr._notebook_to_py_path(notebook_path=nb, repo_root=fake_repo, output_dir="artifacts/gha-nbconvert")
    exctr._convert_notebook(notebook_path=nb, destination_path=dst)
    assert dst.is_file()


def test_diff_first_push(fake_repo: Path) -> None:
    """whether an exception is not raised even when before is ZERO_SHA"""
    nb: Path = fake_repo / "nb" / "test.ipynb"
    subprocess.run(["git", "rm", nb], cwd=fake_repo, check=True)  # Empty git and commit
    subprocess.run(["git", "commit", "-m", "prepare empty"], cwd=fake_repo, check=True)
    after: str = exctr._run_git(args=["rev-parse", "HEAD"], cwd=fake_repo)
    paths: list[Path] = exctr._diff_changed_notebooks(
        repo_root=fake_repo, before="0" * 40, after=after
    )
    # This is the initial push, so there should be no differences.
    assert paths == []


def test_shas_from_pull_request() -> None:
    evt = {
        "pull_request": {
            "base": {"sha": "a"*40},
            "head": {"sha": "b"*40},
        }
    }
    before, after = exctr._shas_from_event(evt, event_name="pull_request")
    assert before == "a"*40
    assert after == "b"*40


def test_is_fork_pr_missing_repo() -> None:
    ev = {
        "pull_request": {"head": {"sha": "b"*40}, "base": {"sha": "a"*40}},
        "repository": {"full_name": "dummy/dummy"},
    }
    assert exctr._is_fork_pr(ev) is False


def test_is_fork_pr_true() -> None:
    ev = {
        "pull_request": {
            "head": {"repo": {"full_name": "someone/fork"}, "sha": "b"*40},
            "base": {"sha": "a"*40},
        },
        "repository": {"full_name": "dummy/dummy"},
    }
    assert exctr._is_fork_pr(ev) is True

def _create_commit(repo: Path, file: Path, msg: str) -> str:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", str(file)], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True)
    return exctr._run_git(args=["rev-parse", "HEAD"], cwd=repo)

def test_diff_two_commits(fake_repo: Path) -> None:
    # 1st: add notebook
    nb = fake_repo / "nb" / "added.ipynb"
    base_sha = _create_commit(fake_repo, nb, "add notebook")
    # 2nd: unrelated change
    readme = fake_repo / "README.md"
    after_sha = _create_commit(fake_repo, readme, "touch readme")
    changed = exctr._diff_changed_notebooks(
        repo_root=fake_repo, before=base_sha, after=after_sha
    )
    assert nb in changed

def test_diff_multi_commits(fake_repo: Path) -> None:
    nb = fake_repo / "nb" / "added.ipynb"
    # Create a commit containing only README in base (main).
    readme = fake_repo / "README.md"
    readme.write_text("base")
    subprocess.run(["git", "add", "."], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "base commit"], cwd=fake_repo, check=True)
    base_sha = exctr._run_git(args=["rev-parse", "HEAD"], cwd=fake_repo)
    # PR: notebook added → README revised
    nb.write_text("{}")
    subprocess.run(["git", "add", str(nb)], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add notebook"], cwd=fake_repo, check=True)
    readme.write_text("edit")
    subprocess.run(["git", "add", str(readme)], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "edit readme"], cwd=fake_repo, check=True)
    head_sha = exctr._run_git(args=["rev-parse", "HEAD"], cwd=fake_repo)

    changed = exctr._diff_changed_notebooks(
        repo_root=fake_repo, before=base_sha, after=head_sha
    )
    assert nb in changed

def test_diff_before_missing(fake_repo: Path) -> None:
    nb = fake_repo / "nb" / "new.ipynb"
    after_sha = _create_commit(fake_repo, nb, "add notebook again")
    changed = exctr._diff_changed_notebooks(
        repo_root=fake_repo, before="a"*40, after=after_sha
    )
    assert nb in changed

def test_diff_handles_nonascii_and_angle_brackets(fake_repo: Path) -> None:
    """Ensure we detect paths with non-ASCII and < > characters (no quoted output)."""
    subdir = fake_repo / "src" / "migration"
    nb = subdir / "日本語_配列_ARRAY<STRING>変換.ipynb"
    nb.parent.mkdir(parents=True, exist_ok=True)
    nb.write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", str(nb)], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add tricky filename"], cwd=fake_repo, check=True)
    before = exctr._run_git(args=["rev-parse", "HEAD~1"], cwd=fake_repo)
    after = exctr._run_git(args=["rev-parse", "HEAD"], cwd=fake_repo)
    changed = exctr._diff_changed_notebooks(repo_root=fake_repo, before=before, after=after)
    assert nb in changed

def test_commit_and_push_is_idempotent(fake_repo: Path, tmp_path: Path) -> None:
    """Second invocation should be a no-op (no new commit, no failure)."""
    # Prepare a bare remote and set as origin so that push works.
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=fake_repo, check=True)
    # Establish upstream for the current branch.
    branch = exctr._run_git(args=["rev-parse", "--abbrev-ref", "HEAD"], cwd=fake_repo)
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=fake_repo, check=True)

    # Convert a notebook and commit/push via the action helper.
    nb = fake_repo / "nb" / "test.ipynb"
    dst = exctr._notebook_to_py_path(notebook_path=nb, repo_root=fake_repo, output_dir="artifacts/gha-nbconvert")
    exctr._convert_notebook(notebook_path=nb, destination_path=dst)
    exctr._commit_and_push(repo_root=fake_repo, files=[dst], branch=branch)
    head1 = exctr._run_git(args=["rev-parse", "HEAD"], cwd=fake_repo)

    # Invoke again without changing inputs; should short-circuit and keep HEAD.
    exctr._commit_and_push(repo_root=fake_repo, files=[dst], branch=branch)
    head2 = exctr._run_git(args=["rev-parse", "HEAD"], cwd=fake_repo)
    assert head1 == head2
