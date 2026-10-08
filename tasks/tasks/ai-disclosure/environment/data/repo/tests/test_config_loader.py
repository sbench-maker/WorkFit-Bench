import json

from src.config_loader import DEFAULT_CAPACITY, load_capacity


def test_blank_environment_uses_default(monkeypatch):
    monkeypatch.setenv("RETRY_BUDGET_CAPACITY", "  ")
    assert load_capacity() == DEFAULT_CAPACITY


def test_file_overrides_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("RETRY_BUDGET_CAPACITY", "20")
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({"retry_budget_capacity": 12}), encoding="utf-8")
    assert load_capacity(config) == 12
