from pathlib import Path

from cosme_monitor.models import Product
from cosme_monitor.state import add_products_to_state, load_state, unseen_products


def test_load_state_returns_empty_when_file_missing(tmp_path: Path) -> None:
    state = load_state(tmp_path / "missing.json")

    assert state.version == 1
    assert state.products == {}


def test_unseen_products_filters_known_entries() -> None:
    known = Product(
        brand="CHANEL",
        product_id="known",
        name="Known",
        price="¥ 1,000",
        currency="JPY",
        image_url="https://example.com/known.jpg",
        product_url="https://example.com/known",
    )
    new = Product(
        brand="CHANEL",
        product_id="new",
        name="New",
        price="¥ 2,000",
        currency="JPY",
        image_url="https://example.com/new.jpg",
        product_url="https://example.com/new",
    )
    state = add_products_to_state(load_state(Path("missing.json")), [known], seen_at="2026-06-05T00:00:00Z")

    unseen = unseen_products([known, new], state)

    assert unseen == [new]
