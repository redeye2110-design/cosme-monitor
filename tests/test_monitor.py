from pathlib import Path

from cosme_monitor.discord import build_discord_payload
from cosme_monitor.models import Product
from cosme_monitor.monitor import MonitorResult, run_monitor


def test_build_discord_payload_uses_price_fallback() -> None:
    product = Product(
        brand="Dior",
        product_id="demo",
        name="ディオール テスト",
        price="",
        currency="JPY",
        image_url="https://example.com/image.jpg",
        product_url="https://example.com/product",
    )

    payload = build_discord_payload(product)

    embed = payload["embeds"][0]
    assert embed["title"] == "Dior 新商品"
    assert embed["fields"][0]["name"] == "価格"
    assert embed["fields"][0]["value"] == "価格未取得"


def test_run_monitor_uses_first_run_as_baseline(tmp_path: Path) -> None:
    sent: list[Product] = []

    def fake_fetcher() -> MonitorResult:
        return MonitorResult(
            products=[
                Product(
                    brand="CHANEL",
                    product_id="107230",
                    name="ブルー ドゥ シャネル",
                    price="¥ 53,790",
                    currency="JPY",
                    image_url="https://example.com/chanel.jpg",
                    product_url="https://example.com/chanel",
                )
            ],
            failures=[],
        )

    result = run_monitor(
        state_file=tmp_path / "seen-products.json",
        fetch_all_products=fake_fetcher,
        notifier=lambda product: sent.append(product),
        now=lambda: "2026-06-05T00:00:00Z",
    )

    assert result.is_baseline is True
    assert result.notified_count == 0
    assert sent == []


def test_run_monitor_notifies_only_unseen_products(tmp_path: Path) -> None:
    sent: list[Product] = []
    state_file = tmp_path / "seen-products.json"

    known = Product(
        brand="CHANEL",
        product_id="known",
        name="Known",
        price="¥ 1,000",
        currency="JPY",
        image_url="https://example.com/known.jpg",
        product_url="https://example.com/known",
    )
    fresh = Product(
        brand="YSL",
        product_id="fresh",
        name="Fresh",
        price="10,890円（税込）",
        currency="JPY",
        image_url="https://example.com/fresh.jpg",
        product_url="https://example.com/fresh",
    )

    run_monitor(
        state_file=state_file,
        fetch_all_products=lambda: MonitorResult(products=[known], failures=[]),
        notifier=lambda product: sent.append(product),
        now=lambda: "2026-06-05T00:00:00Z",
    )

    result = run_monitor(
        state_file=state_file,
        fetch_all_products=lambda: MonitorResult(products=[known, fresh], failures=[]),
        notifier=lambda product: sent.append(product),
        now=lambda: "2026-06-05T00:05:00Z",
    )

    assert result.is_baseline is False
    assert result.notified_count == 1
    assert sent == [fresh]


def test_run_monitor_keeps_successful_brands_when_one_fails(tmp_path: Path) -> None:
    sent: list[Product] = []

    result = run_monitor(
        state_file=tmp_path / "seen-products.json",
        fetch_all_products=lambda: MonitorResult(
            products=[
                Product(
                    brand="CHANEL",
                    product_id="ok",
                    name="Working Product",
                    price="¥ 3,000",
                    currency="JPY",
                    image_url="https://example.com/ok.jpg",
                    product_url="https://example.com/ok",
                )
            ],
            failures=["Dior fetch blocked"],
        ),
        notifier=lambda product: sent.append(product),
        now=lambda: "2026-06-05T00:00:00Z",
    )

    assert result.failures == ["Dior fetch blocked"]
    assert result.product_count == 1


def test_run_monitor_raises_when_all_brands_fail(tmp_path: Path) -> None:
    try:
        run_monitor(
            state_file=tmp_path / "seen-products.json",
            fetch_all_products=lambda: MonitorResult(products=[], failures=["Dior blocked", "CHANEL blocked", "YSL blocked"]),
            notifier=lambda product: None,
            now=lambda: "2026-06-05T00:00:00Z",
        )
    except RuntimeError as error:
        assert "All brand fetches failed" in str(error)
    else:
        raise AssertionError("Expected RuntimeError")
