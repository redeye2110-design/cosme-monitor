from __future__ import annotations

import logging
import random
import re
import time
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
    download_image_bytes: bool = field(default=False)
    # If True, download image bytes via requests after parsing (for non-Playwright brands)


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
    BrandConfig("CHANEL", "https://www.chanel.com/jp/fragrance-beauty/new-arrivals/", parse_chanel_html, download_image_bytes=True),
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
// --- navigator basics ---
Object.defineProperty(navigator, 'webdriver', {get: () => false});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['ja-JP', 'ja', 'en-US', 'en']});
window.chrome = {runtime: {}};
const _origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
window.navigator.permissions.query = (p) =>
  p.name === 'notifications'
    ? Promise.resolve({state: Notification.permission})
    : _origQuery(p);

// --- remove CDP / automation fingerprints ---
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
Object.defineProperty(document, 'hidden', {get: () => false});
Object.defineProperty(document, 'visibilityState', {get: () => 'visible'});

// --- Canvas fingerprint noise (Akamai key signal) ---
const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
  const ctx = this.getContext('2d');
  if (ctx) {
    const imgData = ctx.getImageData(0, 0, this.width || 1, this.height || 1);
    imgData.data[0] ^= 1;
    ctx.putImageData(imgData, 0, 0);
  }
  return _origToDataURL.apply(this, arguments);
};
const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
  const data = _origGetImageData.apply(this, arguments);
  data.data[0] ^= 1;
  return data;
};

// --- WebGL fingerprint: hide SwiftShader (headless GPU) ---
const _origGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(param) {
  if (param === 37445) return 'Intel Inc.';          // UNMASKED_VENDOR_WEBGL
  if (param === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
  return _origGetParameter.call(this, param);
};
try {
  const _origGet2 = WebGL2RenderingContext.prototype.getParameter;
  WebGL2RenderingContext.prototype.getParameter = function(param) {
    if (param === 37445) return 'Intel Inc.';
    if (param === 37446) return 'Intel Iris OpenGL Engine';
    return _origGet2.call(this, param);
  };
} catch(e) {}
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

    _launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-service-autorun",
        "--disable-infobars",
        "--lang=ja-JP",
    ]

    # Priority: system Chrome > Patchright Chromium > plain Playwright Chromium
    # System Chrome has the most authentic fingerprint; Patchright patches binary-level.
    try:
        from patchright.sync_api import sync_playwright as _sync_playwright
    except ImportError:
        from playwright.sync_api import sync_playwright as _sync_playwright  # type: ignore[assignment]

    with _sync_playwright() as p:
        try:
            # 1st choice: system Chrome binary (most authentic fingerprint)
            browser = p.chromium.launch(channel="chrome", headless=True, args=_launch_args)
        except Exception:  # noqa: BLE001
            # 2nd choice: Patchright / Playwright bundled Chromium
            browser = p.chromium.launch(headless=True, args=_launch_args)
        context = browser.new_context(
            user_agent=user_agent,
            locale="ja-JP",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7"},
        )
        context.add_init_script(_STEALTH_SCRIPT)
        page = context.new_page()
        time.sleep(random.uniform(1.0, 3.0))
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=30_000)
            except Exception:  # noqa: BLE001
                pass
        if image_selector:
            try:
                # Collect (pid, src) pairs
                img_data = page.evaluate(f"""
                    () => [...document.querySelectorAll('{image_selector}')].map(img => ({{
                        pid: (img.closest('[data-pid]') || {{}}).dataset?.pid ?? '',
                        src: img.src || img.getAttribute('data-src') || ''
                    }})).filter(x => x.pid && x.src)
                """)
                for item in img_data:
                    pid, src = item["pid"], item["src"]
                    try:
                        # fetch() inside the browser inherits all session cookies
                        raw = page.evaluate("""
                            async (url) => {
                                const r = await fetch(url, {credentials: 'include'});
                                if (!r.ok) return null;
                                const buf = await r.arrayBuffer();
                                return Array.from(new Uint8Array(buf));
                            }
                        """, src)
                        if raw:
                            _playwright_images[pid] = bytes(raw)
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


def _attach_image_bytes(
    products: list[Product],
    session: requests.Session,
    user_agent: str,
    referer: str,
) -> list[Product]:
    import dataclasses
    result = []
    for product in products:
        if product.image_url and not product.image_bytes:
            try:
                resp = session.get(
                    product.image_url,
                    headers={"User-Agent": user_agent, "Referer": referer},
                    timeout=10,
                )
                if resp.ok:
                    product = dataclasses.replace(product, image_bytes=resp.content)
            except Exception:  # noqa: BLE001
                pass
        result.append(product)
    return result


def fetch_all_products(
    session: requests.Session | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    enabled_brands: tuple[str, ...] | list[str] | None = None,
) -> tuple[list[Product], list[str]]:
    own_session = session or requests.Session()
    products: list[Product] = []
    failures: list[str] = []
    for brand in enabled_brand_configs(enabled_brands):
        max_attempts = 2 if brand.use_playwright else 1
        last_error: Exception | None = None
        for attempt in range(max_attempts):
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
                if brand.download_image_bytes:
                    parsed = _attach_image_bytes(parsed, own_session, user_agent, brand.url)
                LOGGER.info("brand=%s url=%s parsed_products=%s attempt=%s", brand.name, brand.url, len(parsed), attempt + 1)
                products.extend(parsed)
                last_error = None
                break
            except Exception as error:  # noqa: BLE001
                last_error = error
                if attempt < max_attempts - 1:
                    wait = random.uniform(8, 15)
                    LOGGER.info("brand=%s attempt=%s blocked, retrying in %.1fs...", brand.name, attempt + 1, wait)
                    time.sleep(wait)
        if last_error is not None:
            message = f"{brand.name} fetch failed: {last_error}"
            LOGGER.warning(message)
            failures.append(message)
        time.sleep(random.uniform(2.0, 5.0))
    return products, failures
