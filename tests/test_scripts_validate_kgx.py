import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from cmm_ai_automation.scripts.validate_kgx import validate


@pytest.fixture
def mock_config(tmp_path: Path) -> Path:
    config = {"custom_prefixes": {"TEST": "http://example.org/test/"}}
    config_file = tmp_path / "config.yaml"
    with config_file.open("w") as f:
        yaml.dump(config, f)
    return config_file


def test_validate_kgx_success(tmp_path: Path, mock_config: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Test validation success path."""
    nodes_file = tmp_path / "nodes.tsv"
    edges_file = tmp_path / "edges.tsv"
    output_file = tmp_path / "report.json"

    # Create dummy files (content doesn't matter as we mock Transformer)
    nodes_file.touch()
    edges_file.touch()

    runner = CliRunner()

    with (
        patch("cmm_ai_automation.scripts.validate_kgx.Validator") as MockValidator,
        patch("cmm_ai_automation.scripts.validate_kgx.Transformer") as MockTransformer,
    ):
        # Setup Mock Validator
        mock_validator_instance = MockValidator.return_value
        mock_validator_instance.prefixes = set()  # Start with empty prefixes
        mock_validator_instance.errors = {}  # No errors

        # Setup Mock Transformer
        mock_transformer_instance = MockTransformer.return_value

        with caplog.at_level(logging.INFO):
            result = runner.invoke(
                validate,
                [
                    "--nodes",
                    str(nodes_file),
                    "--edges",
                    str(edges_file),
                    "--config",
                    str(mock_config),
                    "--output",
                    str(output_file),
                ],
            )

        # Check that custom prefixes were added
        assert "TEST" in mock_validator_instance.prefixes

        # Check that transform was called
        mock_transformer_instance.transform.assert_called_once()

        # Check that report was written
        mock_validator_instance.write_report.assert_called_once()

        assert result.exit_code == 0
        assert "SUCCESS: No validation errors found!" in caplog.text


def test_validate_kgx_failure(tmp_path: Path, mock_config: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Test validation failure path."""
    nodes_file = tmp_path / "nodes.tsv"
    edges_file = tmp_path / "edges.tsv"
    output_file = tmp_path / "report.json"

    nodes_file.touch()
    edges_file.touch()

    runner = CliRunner()

    with (
        patch("cmm_ai_automation.scripts.validate_kgx.Validator") as MockValidator,
        patch("cmm_ai_automation.scripts.validate_kgx.Transformer"),
    ):
        # Setup Mock Validator with errors
        mock_validator_instance = MockValidator.return_value
        mock_validator_instance.prefixes = set()
        mock_validator_instance.errors = {"duplicate_node": {"id:123": ["Node 'id:123' is duplicated"]}}

        with caplog.at_level(logging.ERROR):
            result = runner.invoke(
                validate,
                [
                    "--nodes",
                    str(nodes_file),
                    "--edges",
                    str(edges_file),
                    "--config",
                    str(mock_config),
                    "--output",
                    str(output_file),
                ],
            )

        assert result.exit_code == 1
        assert "FAILURE: Found 1 errors." in caplog.text
