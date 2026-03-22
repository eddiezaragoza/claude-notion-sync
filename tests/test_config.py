import pytest
import json
import os
from notion_sync.config import load_config, get_notion_token


def test_load_config_reads_json(tmp_config):
    config = load_config(tmp_config)
    assert config["databases"]["sessions"] == "db-sessions-id"
    assert config["databases"]["memory"] == "db-memory-id"
    assert config["databases"]["board"] == "db-board-id"
    assert config["pages"]["claude_md_parent"] == "page-claude-md-id"


def test_load_config_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.json")


def test_get_notion_token_from_env(monkeypatch, tmp_config):
    monkeypatch.setenv("NOTION_API_TOKEN", "secret-test-token")
    config = load_config(tmp_config)
    token = get_notion_token(config)
    assert token == "secret-test-token"


def test_get_notion_token_missing_env_raises(monkeypatch, tmp_config):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    config = load_config(tmp_config)
    with pytest.raises(EnvironmentError, match="NOTION_API_TOKEN"):
        get_notion_token(config)
