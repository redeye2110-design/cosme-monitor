from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from cosme_monitor.brands import DEFAULT_USER_AGENT, fetch_all_products as default_fetch_all_products
from cosme_monitor.discord import send_discord_notification
from cosme_monitor.models import Product
from cosme_monitor.state import add_products_to_state, load_state, save_state, unseen_products

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MonitorResult:
    products: list[Product] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    is_baseline: bool = False
    notified_count: int = 0

    @property
    def product_count(self) -> int:
        return len(self.products)


def run_monitor(
    state_file: Path,
    fetch_all_products: Callable[[], MonitorResult] | Callable[[], tuple[list[Product], list[str]]] | None = None,
    notifier: Callable[[Product], None] | None = None,
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

    if not result.products and result.failures:
        raise RuntimeError(f"All brand fetches failed: {', '.join(result.failures)}")

    state = load_state(state_file)
    is_first_run = not state_file.exists()
    fresh_products = unseen_products(result.products, state)

    if is_first_run:
        save_state(state_file, add_products_to_state(state, result.products, seen_at=timestamp))
        LOGGER.info("baseline_created products=%s failures=%s", len(result.products), len(result.failures))
        return MonitorResult(
            products=result.products,
            failures=result.failures,
            is_baseline=True,
            notified_count=0,
        )

    if fresh_products and notifier is None:
        if not webhook_url:
            raise ValueError("webhook_url is required when notifier is not provided")
        notifier = lambda product: send_discord_notification(webhook_url, product)  # noqa: E731

    if notifier is not None:
        for product in fresh_products:
            notifier(product)

    save_state(state_file, add_products_to_state(state, result.products, seen_at=timestamp))
    LOGGER.info(
        "monitor_complete products=%s new_products=%s failures=%s",
        len(result.products),
        len(fresh_products),
        len(result.failures),
    )
    return MonitorResult(
        products=result.products,
        failures=result.failures,
        is_baseline=False,
        notified_count=len(fresh_products),
    )
