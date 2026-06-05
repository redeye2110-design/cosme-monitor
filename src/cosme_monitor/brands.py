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
    use_curl_cffi: bool = field(default=False)
    playwright_image_selector: str | None = field(default=None)
    # CSS selector for <img> inside [data-pid] to download during Playwright scrape


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
    for item in soup.select("div.product[data-pid]"):
        pid = item.get("data-pid", "").strip()
        if not pid:
            continue
        link = item.select_one("a.product-tile__link")
        name_node = item.select_one(".product-tile__name")
        desc_node = item.select_one(".product-tile__short-description")
        price_node = item.select_one(".price .amount") or item.select_one(".price")
        image = item.select_one("img.tile-image")
        if not link or not name_node:
            continue
        parts = [name_node.get_text(" ", strip=True)]
        if desc_node:
            parts.append(desc_node.get_text(" ", strip=True))
        products.append(
            Product(
                brand="Dior",
                product_id=pid,
                name=_clean(" ".join(parts)),
                price=_clean(price_node.get_text(" ", strip=True)) if price_node
                else _price_from_text(item.get_text(" ", strip=True)),
                currency="JPY",
                image_url=image.get("src", "") if image else "",
                product_url=urljoin("https://www.dior.com", link.get("href", "")),
                image_bytes=_get_playwright_image(pid),
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
        playwright_wait_selector="div.product[data-pid]",
        playwright_image_selector="div.product[data-pid] img.tile-image",
    ),
    BrandConfig("CHANEL", "https://www.chanel.com/jp/fragrance-beauty/new-arrivals/", parse_chanel_html),
    BrandConfig(
        "YSL",
        "https://www.yslb.jp/product/limited-collection.html",
        parse_ysl_html,
        use_curl_cffi=True,
    ),
)


def enabled_brand_configs(enabled_brands: tuple[str, ...] | list[str] | None) -> tuple[BrandConfig, ...]:
    if not enabled_brands:
        return BRANDS
    requested = {brand.casefold() for brand in enabled_brands}
    return tuple(brand for brand in BRANDS if brand.name.casefold() in requested)


_BLOCKED_MARKERS = (
    "Page unavailable",
    "Enable JavaScript and cookies to continue",
    "サイト接続の安全性を確認しています",
)


def _fetch_html_curl_cffi(url: str, user_agent: str) -> str:
    from curl_cffi import requests as cffi_requests  # lazy import — optional dep

    response = cffi_requests.get(
        url,
        impersonate="chrome120",
        headers={
            "User-Agent": user_agent,
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        timeout=30,
    )
    response.raise_for_status()
    html = response.text
    if any(marker in html for marker in _BLOCKED_MARKERS):
        raise BrandFetchError("blocked by anti-bot protection")
    return html


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


_playwright_images: dict[str, bytes] = {}


def _get_playwright_image(pid: str) -> bytes:
    return _playwright_images.get(pid, b"")


_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => false});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['ja-JP', 'ja', 'en-US', 'en']});
window.chrome = {runtime: {}};
const _origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
window.navigator.permissions.query = (p) =>
  p.name === 'notifications'
    ? Promise.resolve({state: Notification.permission})
    : _origQuery(p);
"""


def _fetch_html_playwright(
    url: str,
    user_agent: str,
    wait_selector: str | None = None,
    image_selector: str | None = None,
) -> str:
    from playwright.sync_api import sync_playwright  # lazy import — optional dep

    global _playwright_images
    _playwright_images = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=user_agent,
            locale="ja-JP",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7"},
        )
        context.add_init_script(_STEALTH_SCRIPT)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=30_000)
            except Exception:  # noqa: BLE001
                pass
        if image_selector:
            try:
                for img_handle in page.query_selector_all(image_selector):
                    pid = img_handle.evaluate(
                        "el => el.closest('[data-pid]')?.dataset?.pid ?? ''"
                    )
                    src = img_handle.get_attribute("src") or ""
                    if pid and src:
                        try:
                            resp = context.request.get(src, timeout=10_000)
                            if resp.ok:
                                _playwright_images[pid] = bytes(resp.body())
                        except Exception:  # noqa: BLE001
                            pass
            except Exception:  # noqa: BLE001
                pass
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
            if brand.use_curl_cffi:
                html = _fetch_html_curl_cffi(brand.url, user_agent)
            elif brand.use_playwright:
                html = _fetch_html_playwright(
                    brand.url, user_agent,
                    brand.playwright_wait_selector,
                    brand.playwright_image_selector,
                )
            else:
                html = _fetch_html(brand.url, own_session, user_agent)
            parsed = brand.parser(html)
            LOGGER.info("brand=%s url=%s parsed_products=%s", brand.name, brand.url, len(parsed))
            products.extend(parsed)
        except Exception as error:  # noqa: BLE001
            message = f"{brand.name} fetch failed: {error}"
            LOGGER.warning(message)
            failures.append(message)
    return products, failures
