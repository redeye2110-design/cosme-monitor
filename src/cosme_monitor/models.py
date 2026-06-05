from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Product:
    brand: str
    product_id: str
    name: str
    price: str
    currency: str
    image_url: str
    product_url: str

    @property
    def state_key(self) -> str:
        return f"{self.brand}:{self.product_id}"


@dataclass(frozen=True, slots=True)
class Article:
    brand: str
    source: str
    article_id: str
    title: str
    published_at: str
    image_url: str
    article_url: str

    @property
    def state_key(self) -> str:
        return f"article:{self.brand}:{self.source}:{self.article_id}"
