from __future__ import annotations

import json
import time

import requests

from cosme_monitor.models import Article, Product


def build_discord_payload(item: Product | Article, use_attachment: bool = False) -> dict[str, object]:
    if isinstance(item, Product):
        price = item.price or "価格未取得"
        embed: dict[str, object] = {
            "title": f"{item.brand} 新商品",
            "description": item.name,
            "url": item.product_url,
            "fields": [{"name": "価格", "value": price, "inline": True}],
        }
        if use_attachment:
            embed["image"] = {"url": "attachment://product.jpg"}
        elif item.image_url:
            embed["image"] = {"url": item.image_url}
        return {"embeds": [embed]}

    embed = {
        "title": f"{item.brand} 新着記事",
        "description": item.title,
        "url": item.article_url,
        "fields": [
            {"name": "媒体", "value": item.source, "inline": True},
            {"name": "公開日時", "value": item.published_at or "日時未取得", "inline": True},
        ],
    }
    if item.image_url:
        embed["image"] = {"url": item.image_url}
    return {"embeds": [embed]}


def _post(
    session: requests.Session,
    webhook_url: str,
    item: Product | Article,
) -> requests.Response:
    image_bytes = item.image_bytes if isinstance(item, Product) and item.image_bytes else None
    if image_bytes:
        payload = build_discord_payload(item, use_attachment=True)
        return session.post(
            webhook_url,
            data={"payload_json": json.dumps(payload)},
            files={"file": ("product.jpg", image_bytes, "image/jpeg")},
            timeout=60,
        )
    return session.post(webhook_url, json=build_discord_payload(item), timeout=30)


def send_discord_notification(
    webhook_url: str,
    item: Product | Article,
    session: requests.Session | None = None,
) -> None:
    own_session = session or requests.Session()
    response = _post(own_session, webhook_url, item)
    if response.status_code == 429:
        retry_after = float(response.json().get("retry_after", 2))
        time.sleep(retry_after + 0.1)
        response = _post(own_session, webhook_url, item)
    response.raise_for_status()
