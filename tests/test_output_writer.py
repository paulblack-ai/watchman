"""Tests for JSON output writer: file creation, sanitization, schema compliance."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.output.writer import MAX_NAME_LENGTH, _sanitize_filename, write_tool_entry


@pytest.fixture()
def sample_entry() -> IcebreakerToolEntry:
    """Create a sample IcebreakerToolEntry for testing."""
    return IcebreakerToolEntry(
        name="TestTool",
        description="A test tool for AI workflows",
        capabilities=["code generation", "chat"],
        pricing="freemium",
        api_surface="REST API",
        integration_hooks=["Slack"],
        source_url="http://testtool.com",
        discovered_at=datetime(2026, 2, 24),
    )


@pytest.mark.unit
def test_sanitize_filename_special_chars() -> None:
    """Special characters are replaced with underscores, result is lowercase."""
    result = _sanitize_filename("My Tool 2.0!")
    assert result == "my_tool_2_0_"
    assert result.replace("_", "").replace("-", "").isalnum()


@pytest.mark.unit
def test_sanitize_filename_long_name() -> None:
    """Names longer than MAX_NAME_LENGTH are truncated."""
    long_name = "a" * 100
    result = _sanitize_filename(long_name)
    assert len(result) == MAX_NAME_LENGTH


@pytest.mark.unit
def test_write_tool_entry_creates_file(
    tmp_path: Path, sample_entry: IcebreakerToolEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_tool_entry creates a JSON file with correct content."""
    monkeypatch.setenv("WATCHMAN_OUTPUT_DIR", str(tmp_path))
    path = write_tool_entry(sample_entry, card_id=1)
    assert path.exists()
    assert path.name == "testtool_1.json"

    data = json.loads(path.read_text())
    assert data["name"] == "TestTool"
    assert data["description"] == "A test tool for AI workflows"


@pytest.mark.unit
def test_write_tool_entry_creates_directory(
    tmp_path: Path, sample_entry: IcebreakerToolEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_tool_entry creates the output directory if it doesn't exist."""
    output_dir = tmp_path / "nested" / "output"
    monkeypatch.setenv("WATCHMAN_OUTPUT_DIR", str(output_dir))
    path = write_tool_entry(sample_entry, card_id=1)
    assert output_dir.exists()
    assert path.exists()


@pytest.mark.unit
def test_write_tool_entry_no_overwrite(
    tmp_path: Path, sample_entry: IcebreakerToolEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_tool_entry does not overwrite existing files."""
    monkeypatch.setenv("WATCHMAN_OUTPUT_DIR", str(tmp_path))

    # Write first version
    path1 = write_tool_entry(sample_entry, card_id=1)
    original_content = path1.read_text()

    # Modify the entry and write again with same card_id
    modified_entry = IcebreakerToolEntry(
        name="TestTool",
        description="Modified description",
        capabilities=["different"],
    )
    path2 = write_tool_entry(modified_entry, card_id=1)

    assert path1 == path2
    assert path1.read_text() == original_content  # Content unchanged


@pytest.mark.unit
def test_write_tool_entry_json_schema_compliance(
    tmp_path: Path, sample_entry: IcebreakerToolEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Written JSON files round-trip through IcebreakerToolEntry validation."""
    monkeypatch.setenv("WATCHMAN_OUTPUT_DIR", str(tmp_path))
    path = write_tool_entry(sample_entry, card_id=1)

    # Read back and validate
    roundtrip = IcebreakerToolEntry.model_validate_json(path.read_text())
    assert roundtrip.name == sample_entry.name
    assert roundtrip.capabilities == sample_entry.capabilities
    assert roundtrip.pricing == sample_entry.pricing
    assert roundtrip.api_surface == sample_entry.api_surface


@pytest.mark.unit
def test_write_tool_entry_unique_filenames(
    tmp_path: Path, sample_entry: IcebreakerToolEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Different card_ids produce different files even for the same tool name."""
    monkeypatch.setenv("WATCHMAN_OUTPUT_DIR", str(tmp_path))
    path1 = write_tool_entry(sample_entry, card_id=1)
    path2 = write_tool_entry(sample_entry, card_id=2)
    assert path1 != path2
    assert path1.exists()
    assert path2.exists()
