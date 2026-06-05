from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from cosme_monitor.brands import DEFAULT_USER_AGENT, fetch_all_products as default_fetch_all_products
from cosme_monitor.discord import send_discord_notification
from cosme_monitor.models import Article, Product
from cosme_monitor.state import (
    add_articles_to_state,
    add_products_to_state,
    load_state,
    save_state,
    unseen_articles,
    unseen_products,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MonitorResult:
    products: list[Product] = field(default_factory=list)
    articles: list[Article] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    is_baseline: bool = False
    notified_count: int = 0

    @property
    def product_count(self) -> int:
        return len(self.products)

    @property
    def article_count(self) -> int:
        return len(self.articles)


def run_monitor(
    state_file: Path,
    fetch_all_products: Callable[[], MonitorResult] | Callable[[], tuple[list[Product], list[str]]] | None = None,
    notifier: Callable[[Product | Article], None] | None = None,
    now: Callable[[], str] | None = None,
    webhook_url: str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
) -> MonitorResult:
    fetcher = fetch_all_products or (lambda: default_fetch_all_products(user_agent=user_agent))
    timestamp = now() if now else datetime.now(UTC).isoformat()

    raw_result = fetcher()
    if isinstance(raw_result, MonitorResult):
        result = raw_result
    else:
        products, failures = raw_result
        result = MonitorResult(products=products, failures=failures)

    if not result.products and not result.articles and result.failures:
        raise RuntimeError(f"All brand fetches failed: {', '.join(result.failures)}")

    state = load_state(state_file)
    is_first_run = not state_file.exists()
    fresh_products = unseen_products(result.products, state)
    fresh_articles = unseen_articles(result.articles, state)

    if is_first_run:
        baseline_state = add_products_to_state(state, result.products, seen_at=timestamp)
        baseline_state = add_articles_to_state(baseline_state, result.articles, seen_at=timestamp)
        save_state(state_file, baseline_state)
        LOGGER.info(
            "baseline_created products=%s articles=%s failures=%s",
            len(result.products),
            len(result.articles),
            len(result.failures),
        )
        return MonitorResult(
            products=result.products,
            articles=result.articles,
            failures=result.failures,
            is_baseline=True,
            notified_count=0,
        )

    if (fresh_products or fresh_articles) and notifier is None:
        if not webhook_url:
            raise ValueError("webhook_url is required when notifier is not provided")
        notifier = lambda item: send_discord_notification(webhook_url, item)  # noqa: E731

    notified_count = 0
    if notifier is not None:
        for product in fresh_products:
            try:
                notifier(product)
                notified_count += 1
                time.sleep(0.5)
            except Exception as err:  # noqa: BLE001
                LOGGER.warning("notification failed brand=%s product=%s error=%s", product.brand, product.product_id, err)
        for article in fresh_articles:
            try:
                notifier(article)
                notified_count += 1
                time.sleep(0.5)
            except Exception as err:  # noqa: BLE001
                LOGGER.warning("notification failed brand=%s article=%s error=%s", article.brand, article.article_id, err)

    next_state = add_products_to_state(state, result.products, seen_at=timestamp)
    next_state = add_articles_to_state(next_state, result.articles, seen_at=timestamp)
    save_state(state_file, next_state)
    LOGGER.info(
        "monitor_complete products=%s articles=%s new_products=%s new_articles=%s failures=%s",
        len(result.products),
        len(result.articles),
        len(fresh_products),
        len(fresh_articles),
        len(result.failures),
    )
    return MonitorResult(
        products=result.products,
        articles=result.articles,
        failures=result.failures,
        is_baseline=False,
        notified_count=notified_count,
    )
