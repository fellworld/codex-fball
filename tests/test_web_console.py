from pathlib import Path

import pytest

import web_console


def test_resolve_project_path_blocks_parent_escape() -> None:
    with pytest.raises(ValueError):
        web_console.resolve_project_path("../outside.txt")


def test_resolve_project_path_accepts_project_file() -> None:
    resolved = web_console.resolve_project_path("README.md")
    assert resolved == (web_console.PROJECT_ROOT / "README.md").resolve()


def test_file_kind_classifies_supported_views() -> None:
    assert web_console.file_kind(Path("x.csv")) == "csv"
    assert web_console.file_kind(Path("x.md")) == "markdown"
    assert web_console.file_kind(Path("x.py")) == "code"
    assert web_console.file_kind(Path("x.json")) == "json"


def test_commands_are_allowlisted() -> None:
    assert "pytest" in web_console.COMMANDS
    assert all(command.argv[0] for command in web_console.COMMANDS.values())
