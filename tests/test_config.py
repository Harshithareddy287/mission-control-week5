import os
from pathlib import Path

from app import config


def test_dotenv_skipped_in_tests():
    assert os.environ.get("MISSION_CONTROL_SKIP_DOTENV") == "1"
    assert config.load_env_file() is False
    assert config.OPENAI_API_KEY is None


def test_dotenv_loaded_without_overriding(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MC_TEST_FROM_FILE=file\nMC_TEST_ALREADY_SET=file\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.delenv("MISSION_CONTROL_SKIP_DOTENV")
    monkeypatch.setenv("MC_TEST_ALREADY_SET", "env")
    monkeypatch.delenv("MC_TEST_FROM_FILE", raising=False)
    try:
        assert config.load_env_file() is True
        assert os.environ["MC_TEST_FROM_FILE"] == "file"
        assert os.environ["MC_TEST_ALREADY_SET"] == "env"  # existing value wins
    finally:
        os.environ.pop("MC_TEST_FROM_FILE", None)


def test_missing_dotenv_is_fine(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "nope.env")
    monkeypatch.delenv("MISSION_CONTROL_SKIP_DOTENV")
    assert config.load_env_file() is False


def test_env_example_has_placeholders_only():
    example = Path(config.__file__).resolve().parent.parent / ".env.example"
    values = dict(
        line.split("=", 1) for line in example.read_text().splitlines()
        if line and not line.startswith("#")
    )
    assert set(values) == {"LLM_PROVIDER", "MODEL_NAME", "OPENAI_BASE_URL", "OPENAI_API_KEY"}
    assert values["OPENAI_API_KEY"] == "your-api-key-here"
