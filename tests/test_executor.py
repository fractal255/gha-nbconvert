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
