from __future__ import annotations

import logging
from pathlib import Path

from cosme_monitor.article_sources import fetch_all_articles
from cosme_monitor.brands import fetch_all_products
from cosme_monitor.config import load_runtime_config
from cosme_monitor.monitor import MonitorResult, run_monitor


def _fetch_all_content(
    enabled_brands: tuple[str, ...],
    enabled_article_brands: tuple[str, ...],
) -> MonitorResult:
    products, product_failures = fetch_all_products(enabled_brands=enabled_brands)
    articles, article_failures = fetch_all_articles(enabled_brands=enabled_article_brands)
    return MonitorResult(
        products=products,
        articles=articles,
        failures=product_failures + article_failures,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_runtime_config()
    state_file = Path(config.state_file)
    result = run_monitor(
        state_file=state_file,
        webhook_url=config.webhook_url,
        fetch_all_products=lambda: _fetch_all_content(
            enabled_brands=config.enabled_brands,
            enabled_article_brands=config.enabled_article_brands,
        ),
    )
    logging.info(
        "done baseline=%s products=%s articles=%s notified=%s failures=%s enabled_brands=%s enabled_article_brands=%s",
        result.is_baseline,
        result.product_count,
        result.article_count,
        result.notified_count,
        len(result.failures),
        ",".join(config.enabled_brands),
        ",".join(config.enabled_article_brands),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
