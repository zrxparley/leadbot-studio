from app.core.config import DEFAULT_ENV_FILE, PROJECT_ROOT, Settings


def test_default_env_file_is_project_root_env():
    assert PROJECT_ROOT.name == "LeadBot"
    assert DEFAULT_ENV_FILE == PROJECT_ROOT / ".env"


def test_settings_can_load_env_file_independent_of_cwd(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LEADBOT_DRAFT_PROVIDER=openai",
                "LEADBOT_DRAFT_MODEL=gpt-5.4-mini",
                "OPENAI_API_KEY=test-key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    class TempSettings(Settings):
        model_config = Settings.model_config.copy()
        model_config["env_file"] = env_file

    settings = TempSettings()

    assert settings.leadbot_draft_provider == "openai"
    assert settings.leadbot_draft_model == "gpt-5.4-mini"
    assert settings.openai_api_key == "test-key"


def test_env_file_can_be_overridden_by_environment_variable(tmp_path, monkeypatch):
    env_file = tmp_path / "custom.env"
    env_file.write_text("LEADBOT_DRAFT_PROVIDER=openai\n", encoding="utf-8")
    monkeypatch.setenv("LEADBOT_ENV_FILE", str(env_file))

    from importlib import reload
    import app.core.config as config_module

    reload(config_module)
    settings = config_module.Settings()

    assert settings.leadbot_draft_provider == "openai"
    monkeypatch.delenv("LEADBOT_ENV_FILE")
    reload(config_module)
