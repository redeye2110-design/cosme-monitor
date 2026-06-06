from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from cosme_monitor.brands import DEFAULT_USER_AGENT
from cosme_monitor.models import Article

LOGGER = logging.getLogger(__name__)

PRTIMES_BASE_URL = "https://prtimes.jp"
FASHIONSNAP_BASE_URL = "https://www.fashionsnap.com"
FASHIONSNAP_BEAUTY_NEWS_URL = "https://www.fashionsnap.com/article/news/beauty/?category=%E3%83%93%E3%83%A5%E3%83%BC%E3%83%86%E3%82%A3"


@dataclass(frozen=True, slots=True)
class PrtimesSourceConfig:
    brand: str
    company_id: int

    @property
    def url(self) -> str:
        return f"{PRTIMES_BASE_URL}/api/company_content.php/companies/{self.company_id}/press_releases"


PRTIMES_SOURCES = (
    PrtimesSourceConfig(brand="Dior", company_id=14810),
    PrtimesSourceConfig(brand="YSL", company_id=32072),
    PrtimesSourceConfig(brand="CHANEL", company_id=150142),
)

FASHIONSNAP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Dior": ("Dior", "ディオール"),
    "YSL": ("YSL", "イヴ・サンローラン", "サンローラン"),
    "CHANEL": ("CHANEL", "シャネル"),
}


def _clean(text: str) -> str:
    return " ".join(text.split())


def _matches_keyword(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.casefold()
    return any(keyword.casefold() in lowered for keyword in keywords)


def parse_prtimes_articles_payload(
    payload: dict,
    brand: str,
    source_label: str = "PR TIMES",
) -> list[Article]:
    entries = payload.get("data", {}).get("data", [])
    articles: list[Article] = []
    for entry in entries:
        article_id = str(entry.get("id", "")).strip()
        title = _clean(entry.get("title", ""))
        url = urljoin(PRTIMES_BASE_URL, entry.get("url", ""))
        image_url = (
            entry.get("thumbs", {}).get("s")
            or entry.get("thumbs", {}).get("m")
            or entry.get("thumbs", {}).get("l")
            or ""
        )
        updated = entry.get("updated_at", {})
        published_at = (
            updated.get("time_iso_8601")
            or updated.get("origin")
            or updated.get("time_ago")
            or ""
        )
        if not article_id or not title or not url:
            continue
        articles.append(
            Article(
                brand=brand,
                source=source_label,
                article_id=article_id,
                title=title,
                published_at=published_at,
                image_url=image_url,
                article_url=url,
            )
        )
    return articles


def filter_fashionsnap_articles(
    html: str,
    brand: str,
    keywords: Iterable[str],
) -> list[Article]:
    soup = BeautifulSoup(html, "html.parser")
    articles: list[Article] = []
    seen_ids: set[str] = set()
    for card in soup.select("div._144h2oc0"):
        title_node = card.select_one("p._144h2oc1")
        link = card.select_one("a[href^='/article/']")
        time_node = card.select_one("time[dateTime]")
        image = card.select_one("img")
        if not title_node or not link:
            continue
        title = _clean(title_node.get_text(" ", strip=True))
        if not _matches_keyword(title, keywords):
            continue
        href = link.get("href", "")
        article_id = href.removeprefix("/article/").strip("/")
        if not article_id or article_id in seen_ids:
            continue
        seen_ids.add(article_id)
        articles.append(
            Article(
                brand=brand,
                source="FASHIONSNAP",
                article_id=article_id,
                title=title,
                published_at=time_node.get("dateTime", "") if time_node else "",
                image_url=image.get("src", "") if image else "",
                article_url=urljoin(FASHIONSNAP_BASE_URL, href),
            )
        )
    return articles


def _fetch_prtimes_articles(
    source: PrtimesSourceConfig,
    session: requests.Session,
    user_agent: str,
) -> list[Article]:
    response = session.get(
        source.url,
        params={"limit": 20},
        timeout=30,
        headers={
            "User-Agent": user_agent,
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    response.raise_for_status()
    payload = response.json()
    articles = parse_prtimes_articles_payload(payload=payload, brand=source.brand)
    LOGGER.info("source=PR TIMES brand=%s parsed_articles=%s", source.brand, len(articles))
    return articles


def _fetch_fashionsnap_html(session: requests.Session, user_agent: str) -> str:
    response = session.get(
        FASHIONSNAP_BEAUTY_NEWS_URL,
        timeout=30,
        headers={
            "User-Agent": user_agent,
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    response.raise_for_status()
    return response.text


def enabled_article_brands(enabled_brands: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if not enabled_brands:
        return ("Dior", "YSL", "CHANEL")
    requested = {brand.casefold() for brand in enabled_brands}
    return tuple(
        source.brand
        for source in PRTIMES_SOURCES
        if source.brand.casefold() in requested
    )


def fetch_all_articles(
    session: requests.Session | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    enabled_brands: tuple[str, ...] | list[str] | None = None,
) -> tuple[list[Article], list[str]]:
    own_session = session or requests.Session()
    requested_brands = enabled_article_brands(enabled_brands)
    if not requested_brands:
        return [], []

    articles: list[Article] = []
    failures: list[str] = []

    for source in PRTIMES_SOURCES:
        if source.brand not in requested_brands:
            continue
        try:
            articles.extend(_fetch_prtimes_articles(source, own_session, user_agent))
        except Exception as error:  # noqa: BLE001
            message = f"{source.brand} PR TIMES fetch failed: {error}"
            LOGGER.warning(message)
            failures.append(message)

    try:
        fashionsnap_html = _fetch_fashionsnap_html(own_session, user_agent)
        for brand in requested_brands:
            keywords = FASHIONSNAP_KEYWORDS.get(brand, ())
            if not keywords:
                continue
            parsed = filter_fashionsnap_articles(
                html=fashionsnap_html,
                brand=brand,
                keywords=keywords,
            )
            LOGGER.info("source=FASHIONSNAP brand=%s parsed_articles=%s", brand, len(parsed))
            articles.extend(parsed)
    except Exception as error:  # noqa: BLE001
        message = f"FASHIONSNAP fetch failed: {error}"
        LOGGER.warning(message)
        failures.append(message)

    return articles, failures
