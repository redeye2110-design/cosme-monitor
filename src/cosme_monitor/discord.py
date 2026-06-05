from __future__ import annotations

import requests

from cosme_monitor.models import Product


def build_discord_payload(product: Product) -> dict[str, object]:
    price = product.price or "価格未取得"
    return {
        "embeds": [
            {
                "title": f"{product.brand} 新商品",
                "description": product.name,
                "url": product.product_url,
                "image": {"url": product.image_url},
                "fields": [{"name": "価格", "value": price, "inline": True}],
            }
        ]
    }


def send_discord_notification(
    webhook_url: str,
    product: Product,
    session: requests.Session | None = None,
) -> None:
    own_session = session or requests.Session()
    response = own_session.post(webhook_url, json=build_discord_payload(product), timeout=30)
    response.raise_for_status()
