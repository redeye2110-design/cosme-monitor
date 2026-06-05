from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cosme_monitor.models import Product


@dataclass(slots=True)
class SeenState:
    version: int = 1
    products: dict[str, dict[str, str]] = field(default_factory=dict)


def load_state(path: Path) -> SeenState:
    if not path.exists():
        return SeenState()

    payload = json.loads(path.read_text(encoding="utf-8"))
    return SeenState(
        version=int(payload.get("version", 1)),
        products=dict(payload.get("products", {})),
    )


def save_state(path: Path, state: SeenState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": state.version,
        "products": state.products,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_products_to_state(state: SeenState, products: list[Product], seen_at: str) -> SeenState:
    merged = dict(state.products)
    for product in products:
        merged[product.state_key] = {
            "brand": product.brand,
            "name": product.name,
            "first_seen_at": merged.get(product.state_key, {}).get("first_seen_at", seen_at),
        }
    return SeenState(version=state.version, products=merged)


def unseen_products(products: list[Product], state: SeenState) -> list[Product]:
    return [product for product in products if product.state_key not in state.products]
