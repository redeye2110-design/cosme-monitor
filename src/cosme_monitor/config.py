from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    webhook_url: str
    state_file: str
    enabled_brands: tuple[str, ...]
    enabled_article_brands: tuple[str, ...]


def load_runtime_config() -> RuntimeConfig:
    raw_enabled = os.environ.get("ENABLED_BRANDS", "CHANEL")
    raw_enabled_article_brands = os.environ.get("ENABLED_ARTICLE_BRANDS", "DIOR,YSL")
    enabled_brands = tuple(part.strip() for part in raw_enabled.split(",") if part.strip())
    enabled_article_brands = tuple(part.strip() for part in raw_enabled_article_brands.split(",") if part.strip())
    return RuntimeConfig(
        webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", ""),
        state_file=os.environ.get("STATE_FILE", "seen-products.json"),
        enabled_brands=enabled_brands or ("CHANEL",),
        enabled_article_brands=enabled_article_brands or ("DIOR", "YSL"),
    )
