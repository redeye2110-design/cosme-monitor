from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from cosme_monitor.models import Product

LOGGER = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PRICE_RE = re.compile(r"(¥\s?[\d,]+(?:\s?から)?)|([\d,]+円(?:（税込）)?)")


class BrandFetchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BrandConfig:
    name: str
    url: str
    parser: Callable[[str], list[Product]]
    use_playwright: bool = field(default=False)
    playwright_wait_selector: str | None = field(default=None)


def _clean(text: str) -> str:
    return " ".join(text.split())


def _price_from_text(text: str) -> str:
    match = PRICE_RE.search(text)
    return _clean(match.group(0)) if match else ""


def _extract_image(node: BeautifulSoup, *attrs: str) -> str:
    for attr in attrs:
        value = node.get(attr)
        if value:
            return value
    return ""


def parse_dior_html(html: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    products: list[Product] = []
    for card in soup.select("article.product-card"):
        link = card.select_one("a.product-card__link")
        name = card.select_one(".product-card__name")
        image = card.select_one("img.product-card__image")
        if not link or not name:
            continue
        product_id = card.get("data-product-id") or link.get("href", "").rstrip("/").split("/")[-1]
        products.append(
            Product(
                brand="Dior",
                product_id=product_id,
                name=_clean(name.get_text(" ", strip=True)),
                price=_clean(card.select_one(".product-card__price").get_text(" ", strip=True))
                if card.select_one(".product-card__price")
                else _price_from_text(card.get_text(" ", strip=True)),
                currency="JPY",
                image_url=_extract_image(image, "src", "data-src") if image else "",
                product_url=urljoin("https://www.dior.com", link.get("href", "")),
            )
        )
    return products


def parse_chanel_html(html: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    products: list[Product] = []
    for article in soup.select("div.product-grid__item article.product"):
        link = article.select_one("a[data-test='product_link']")
        title = article.select_one(".txt-product__title")
        description = article.select_one("[data-product-element='description']")
        image = article.select_one("img")
        if not link or not title:
            continue
        parts = [title.get_text(" ", strip=True)]
        if description:
            parts.append(description.get_text(" ", strip=True))
        products.append(
            Product(
                brand="CHANEL",
                product_id=article.get("data-id", ""),
                name=_clean(" ".join(parts)),
                price=_price_from_text(article.get_text(" ", strip=True)),
                currency="JPY",
                image_url=_extract_image(image, "data-src", "src") if image else "",
                product_url=urljoin("https://www.chanel.com", link.get("href", "")),
            )
        )
    return products


def parse_ysl_html(html: str) -> list[Product]:
    soup = BeautifulSoup(html, "html.parser")
    products: list[Product] = []
    for item in soup.select("[data-pid]"):
        pid = item.get("data-pid", "").strip()
        if not pid:
            continue
        link = item.select_one("a[href]")
        name_node = item.select_one(".c-product-tile__name")
        variation_node = item.select_one(".c-product-tile__variation")
        image = item.select_one("img")
        if not link or not name_node:
            continue
        parts = [name_node.get_text(" ", strip=True)]
        if variation_node:
            parts.append(variation_node.get_text(" ", strip=True))
        products.append(
            Product(
                brand="YSL",
                product_id=pid,
                name=_clean(" ".join(parts)),
                price=_clean(item.select_one(".c-product-tile__price").get_text(" ", strip=True))
                if item.select_one(".c-product-tile__price")
                else _price_from_text(item.get_text(" ", strip=True)),
                currency="JPY",
                image_url=_extract_image(image, "src", "data-src") if image else "",
                product_url=urljoin("https://www.yslb.jp", link.get("href", "")),
            )
        )
    return products


BRANDS = (
    BrandConfig(
        "Dior",
        "https://www.dior.com/ja_jp/beauty/page/all-new-arrivals.html",
        parse_dior_html,
        use_playwright=True,
        playwright_wait_selector="article.product-card",
    ),
    BrandConfig("CHANEL", "https://www.chanel.com/jp/fragrance-beauty/new-arrivals/", parse_chanel_html),
    BrandConfig(
        "YSL",
        "https://www.yslb.jp/product/limited-collection.html",
        parse_ysl_html,
        use_playwright=True,
        playwright_wait_selector="[data-pid]",
    ),
)


def enabled_brand_configs(enabled_brands: tuple[str, ...] | list[str] | None) -> tuple[BrandConfig, ...]:
    if not enabled_brands:
        return BRANDS
    requested = {brand.casefold() for brand in enabled_brands}
    return tuple(brand for brand in BRANDS if brand.name.casefold() in requested)


def _log_html_debug(brand_name: str, html: str) -> None:
    """Log inner structure of first [data-pid] product to identify field selectors."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div[data-pid]")
    if not items:
        LOGGER.warning("brand=%s no div[data-pid] found; html_len=%s", brand_name, len(html))
        return
    LOGGER.warning("brand=%s div[data-pid] hits=%s", brand_name, len(items))
    first = items[0]
    # log all descendant tags with classes, attrs, and text snippets
    for el in first.find_all(True)[:40]:
        text = " ".join(el.get_text(" ", strip=True).split())[:60]
        LOGGER.warning(
            "brand=%s  <%s class=%r attrs=%r text=%r",
            brand_name, el.name, el.get("class"), {k: v for k, v in el.attrs.items() if k != "class"}, text,
        )


_BLOCKED_MARKERS = (
    "Page unavailable",
    "Enable JavaScript and cookies to continue",
    "サイト接続の安全性を確認しています",
)


def _fetch_html(url: str, session: requests.Session, user_agent: str) -> str:
    response = session.get(
        url,
        timeout=30,
        headers={
            "User-Agent": user_agent,
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    response.raise_for_status()
    html = response.text
    if any(marker in html for marker in _BLOCKED_MARKERS):
        raise BrandFetchError("blocked by anti-bot protection")
    return html


def _fetch_html_playwright(url: str, user_agent: str, wait_selector: str | None = None) -> str:
    from playwright.sync_api import sync_playwright  # lazy import — optional dep

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=user_agent,
            locale="ja-JP",
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7"},
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=30_000)
            except Exception:  # noqa: BLE001
                pass  # proceed with whatever rendered so far
        html = page.content()
        context.close()
        browser.close()

    if any(marker in html for marker in _BLOCKED_MARKERS):
        raise BrandFetchError("blocked by anti-bot protection")
    return html


def fetch_all_products(
    session: requests.Session | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    enabled_brands: tuple[str, ...] | list[str] | None = None,
) -> tuple[list[Product], list[str]]:
    own_session = session or requests.Session()
    products: list[Product] = []
    failures: list[str] = []
    for brand in enabled_brand_configs(enabled_brands):
        try:
            if brand.use_playwright:
                html = _fetch_html_playwright(brand.url, user_agent, brand.playwright_wait_selector)
            else:
                html = _fetch_html(brand.url, own_session, user_agent)
            parsed = brand.parser(html)
            LOGGER.info("brand=%s url=%s parsed_products=%s", brand.name, brand.url, len(parsed))
            if len(parsed) == 0 and brand.use_playwright:
                _log_html_debug(brand.name, html)
            products.extend(parsed)
        except Exception as error:  # noqa: BLE001
            message = f"{brand.name} fetch failed: {error}"
            LOGGER.warning(message)
            failures.append(message)
    return products, failures
