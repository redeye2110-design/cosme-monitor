from __future__ import annotations

import logging
from pathlib import Path

from cosme_monitor.config import load_runtime_config
from cosme_monitor.monitor import run_monitor
from cosme_monitor.brands import fetch_all_products


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_runtime_config()
    state_file = Path(config.state_file)
    result = run_monitor(
        state_file=state_file,
        webhook_url=config.webhook_url,
        fetch_all_products=lambda: fetch_all_products(enabled_brands=config.enabled_brands),
    )
    logging.info(
        "done baseline=%s products=%s notified=%s failures=%s enabled_brands=%s",
        result.is_baseline,
        result.product_count,
        result.notified_count,
        len(result.failures),
        ",".join(config.enabled_brands),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
