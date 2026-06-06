from cosme_monitor.config import RuntimeConfig, load_runtime_config


def test_load_runtime_config_defaults_to_chanel_only(monkeypatch) -> None:
    monkeypatch.delenv("ENABLED_BRANDS", raising=False)
    monkeypatch.delenv("ENABLED_ARTICLE_BRANDS", raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")

    config = load_runtime_config()

    assert config == RuntimeConfig(
        webhook_url="https://discord.example/webhook",
        state_file="seen-products.json",
        enabled_brands=("CHANEL",),
        enabled_article_brands=("DIOR", "YSL", "CHANEL"),
    )


def test_load_runtime_config_accepts_multiple_brands(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    monkeypatch.setenv("STATE_FILE", "custom-state.json")
    monkeypatch.setenv("ENABLED_BRANDS", "CHANEL, Dior ,YSL")
    monkeypatch.setenv("ENABLED_ARTICLE_BRANDS", "Dior,YSL,CHANEL")

    config = load_runtime_config()

    assert config.enabled_brands == ("CHANEL", "Dior", "YSL")
    assert config.enabled_article_brands == ("Dior", "YSL", "CHANEL")
    assert config.state_file == "custom-state.json"
