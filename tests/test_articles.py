import json
from pathlib import Path

from cosme_monitor.article_sources import (
    filter_fashionsnap_articles,
    parse_prtimes_articles_payload,
)
from cosme_monitor.discord import build_discord_payload
from cosme_monitor.models import Article


def _fixture_text(name: str) -> str:
    return Path("tests/fixtures", name).read_text(encoding="utf-8")


def _fixture_json(name: str) -> dict:
    return json.loads(_fixture_text(name))


def test_parse_prtimes_articles_payload_extracts_articles() -> None:
    payload = _fixture_json("prtimes_company_articles.json")

    articles = parse_prtimes_articles_payload(
        payload=payload,
        brand="Dior",
        source_label="PR TIMES",
    )

    assert len(articles) == 2
    assert articles[0].brand == "Dior"
    assert articles[0].source == "PR TIMES"
    assert articles[0].article_id == "631"
    assert articles[0].title == "「ディオール フォーエヴァー」新製品の誕生を祝い新木優子、山下智久らが来場"
    assert articles[0].article_url == "https://prtimes.jp/main/html/rd/p/000000631.000014810.html"
    assert articles[0].image_url == "https://example.com/dior-631.jpg"


def test_parse_prtimes_articles_payload_extracts_chanel_articles() -> None:
    payload = _fixture_json("prtimes_chanel_articles.json")

    articles = parse_prtimes_articles_payload(
        payload=payload,
        brand="CHANEL",
        source_label="PR TIMES",
    )

    assert len(articles) == 2
    assert articles[0].brand == "CHANEL"
    assert articles[0].article_id == "12"
    assert articles[0].title == "シャネル「カメリア フトゥーラ」数量限定コレクションを発売"
    assert articles[0].article_url == "https://prtimes.jp/main/html/rd/p/000000012.000150142.html"
    assert articles[0].image_url == "https://example.com/chanel-12.jpg"


def test_filter_fashionsnap_articles_matches_brand_keywords() -> None:
    html = _fixture_text("fashionsnap_beauty_articles.html")

    articles = filter_fashionsnap_articles(
        html=html,
        brand="YSL",
        keywords=("YSL", "イヴ・サンローラン", "サンローラン"),
    )

    assert len(articles) == 1
    assert articles[0].brand == "YSL"
    assert articles[0].source == "FASHIONSNAP"
    assert articles[0].article_id == "2026-06-02/ysl-loveshine"
    assert articles[0].title == "YSL「ラブシャイン」から新作リップが登場"
    assert articles[0].article_url == "https://www.fashionsnap.com/article/2026-06-02/ysl-loveshine/"
    assert articles[0].image_url == "https://example.com/ysl-loveshine.jpg"


def test_filter_fashionsnap_articles_matches_chanel_keywords() -> None:
    html = _fixture_text("fashionsnap_beauty_articles.html")

    articles = filter_fashionsnap_articles(
        html=html,
        brand="CHANEL",
        keywords=("CHANEL", "シャネル"),
    )

    assert len(articles) == 1
    assert articles[0].brand == "CHANEL"
    assert articles[0].source == "FASHIONSNAP"
    assert articles[0].article_id == "2026-06-04/chanel-camelia-futura"
    assert articles[0].title == "CHANEL「カメリア フトゥーラ」から限定メイクアップが登場"
    assert articles[0].article_url == "https://www.fashionsnap.com/article/2026-06-04/chanel-camelia-futura/"
    assert articles[0].image_url == "https://example.com/chanel-camelia-futura.jpg"


def test_build_discord_payload_for_article() -> None:
    article = Article(
        brand="Dior",
        source="PR TIMES",
        article_id="631",
        title="ディオール新作記事",
        published_at="2026-06-04T11:04:11+09:00",
        image_url="https://example.com/dior.jpg",
        article_url="https://example.com/dior-article",
    )

    payload = build_discord_payload(article)

    embed = payload["embeds"][0]
    assert embed["title"] == "Dior 新着記事"
    assert embed["description"] == "ディオール新作記事"
    assert embed["fields"][0]["name"] == "媒体"
    assert embed["fields"][0]["value"] == "PR TIMES"
    assert embed["fields"][1]["name"] == "公開日時"
    assert embed["fields"][1]["value"] == "2026-06-04T11:04:11+09:00"
