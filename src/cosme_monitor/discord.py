from __future__ import annotations

import time

import requests

from cosme_monitor.models import Article, Product


def build_discord_payload(item: Product | Article) -> dict[str, object]:
    if isinstance(item, Product):
        price = item.price or "価格未取得"
        embed: dict[str, object] = {
            "title": f"{item.brand} 新商品",
            "description": item.name,
            "url": item.product_url,
            "fields": [{"name": "価格", "value": price, "inline": True}],
        }
        if item.image_url:
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


def send_discord_notification(
    webhook_url: str,
    item: Product | Article,
    session: requests.Session | None = None,
) -> None:
    own_session = session or requests.Session()
    response = own_session.post(webhook_url, json=build_discord_payload(item), timeout=30)
    if response.status_code == 429:
        retry_after = float(response.json().get("retry_after", 2))
        time.sleep(retry_after + 0.1)
        response = own_session.post(webhook_url, json=build_discord_payload(item), timeout=30)
    response.raise_for_status()
