from pathlib import Path

from cosme_monitor.brands import (
    enabled_brand_configs,
    parse_chanel_html,
    parse_dior_html,
    parse_ysl_html,
)


def _fixture(name: str) -> str:
    return Path("tests/fixtures", name).read_text(encoding="utf-8")


def test_parse_dior_html_extracts_products() -> None:
    products = parse_dior_html(_fixture("dior_new_arrivals.html"))

    assert len(products) == 2
    assert products[0].brand == "Dior"
    assert products[0].product_id == "Y0000225"
    assert products[0].name == "ミス ディオール ハンド クリーム ブルーミング ブーケ香るハンド クリーム"
    assert products[0].price == "¥ 8,250"
    assert products[0].image_url == "https://www.dior.com/dw/image/v2/Y0000225.jpg"
    assert "Y0000225" in products[0].product_url


def test_parse_chanel_html_extracts_products() -> None:
    products = parse_chanel_html(_fixture("chanel_new_arrivals.html"))

    assert len(products) == 2
    assert products[0].brand == "CHANEL"
    assert products[0].product_id == "107230"
    assert products[0].name == "ブルー ドゥ シャネル レゼクスクルジフ"
    assert products[0].price == "¥ 53,790"
    assert products[0].product_url.endswith("/jp/fragrance/p/107230/bleu-de-chanel-lexclusif-parfum-spray/")


def test_parse_ysl_html_extracts_products() -> None:
    products = parse_ysl_html(_fixture("ysl_new_arrivals.html"))

    assert len(products) == 2
    assert products[0].brand == "YSL"
    assert products[0].product_id == "ysl-740"
    assert products[0].name == "クチュール ミニ クラッチ No.740 エンドレス スパーク"
    assert products[0].price == "10,890円（税込）"
    assert products[0].image_url == "https://www.yslb.jp/images/ysl-740.jpg"
    assert products[0].product_url == "https://www.yslb.jp/product/limited/ysl-740.html"


def test_enabled_brand_configs_filters_to_requested_brands() -> None:
    brands = enabled_brand_configs(("CHANEL", "YSL"))

    assert [brand.name for brand in brands] == ["CHANEL", "YSL"]
