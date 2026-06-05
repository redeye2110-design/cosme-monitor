# Cosmetics New Arrivals Monitor Design

Date: 2026-06-05

## Goal

Build a fully free monitor for new cosmetics arrivals from Dior, CHANEL, and YSL.
The system runs every 5 minutes on GitHub Actions, detects newly listed products, and posts Discord notifications with product name, price, image, and product URL.

## Scope

In scope:

- Monitor official new-arrivals pages for Dior, CHANEL, and YSL
- Extract product name, price, image URL, and product URL
- Persist previously seen product IDs
- Send Discord embed notifications only for newly discovered products
- Skip notifications on the first successful run and use it as the baseline
- Run on GitHub Actions with public repository assumptions

Out of scope:

- Restock monitoring
- LINE integration
- Browser automation
- Historical database beyond the current seen-state file
- Admin UI or dashboard

## Approach

Use a Python command-line script as the single entry point.
The script fetches each brand page over HTTP, parses the product list, normalizes products into a shared schema, compares them with the persisted seen-state, sends Discord notifications for unseen products, and then updates the seen-state.

This is the recommended first version because it keeps the system cheap, testable, and easy to move to another runner later.

## Architecture

### Runtime

- Python 3.12
- GitHub Actions scheduled workflow every 5 minutes
- Discord incoming webhook stored in GitHub Secrets

### Modules

- `src/monitor.py`
  Main orchestration entry point
- `src/brands.py`
  Brand-specific scraping logic and normalization
- `src/models.py`
  Shared product schema and serialization helpers
- `src/state.py`
  Load/save seen product state from JSON
- `src/discord.py`
  Build and send Discord embeds
- `tests/`
  Unit tests for parsing, diffing, and notification payloads

## Product Model

Each discovered item is normalized into:

- `brand`
- `product_id`
- `name`
- `price`
- `currency`
- `image_url`
- `product_url`

`product_id` is the stable dedupe key. It should prefer a canonical product URL or official product code when available. If neither exists, use a deterministic hash from brand plus normalized name plus product URL.

## Brand Scraping Strategy

Each brand gets one parser function:

- `fetch_dior_products()`
- `fetch_chanel_products()`
- `fetch_ysl_products()`

Each parser:

- fetches only the designated new-arrivals page
- extracts the visible product cards
- resolves relative URLs into absolute URLs
- trims and normalizes text fields
- returns a list of normalized products

The implementation should start with plain HTTP and HTML parsing. If one brand later requires JavaScript rendering, only that brand adapter should change.

## State Management

Use `seen-products.json` in the repository root.

Structure:

```json
{
  "version": 1,
  "products": {
    "brand:product-id": {
      "brand": "Dior",
      "name": "Example",
      "first_seen_at": "2026-06-05T12:00:00Z"
    }
  }
}
```

Rules:

- first successful run creates or updates the state file without sending notifications
- later runs notify only products absent from the stored map
- after successful notifications, newly seen products are written back to disk

## Notification Format

Use one Discord embed per product.

Embed fields:

- title: `<Brand> 新商品`
- description: product name
- URL: product URL
- image: product image URL
- field: `価格`

If `price` is unavailable, set the field value to `価格未取得`.

## Execution Flow

1. Load configuration from environment variables
2. Load existing seen-state, if present
3. Fetch and parse all brand pages
4. Merge results into one normalized product list
5. Compute unseen products by `brand:product_id`
6. If no state exists yet, save baseline and exit without notifications
7. Send Discord notifications for unseen products
8. Save updated seen-state
9. Exit non-zero only for hard failures that should fail the workflow

## Error Handling

Rules:

- one brand failing should not discard successful results from the others
- a total failure across all brands should fail the run
- Discord delivery failure should fail the run so it is visible in Actions
- malformed individual cards should be skipped, not crash the whole brand parser

Logging:

- English logs only
- include brand name, fetched URL, number of parsed products, number of new products, and failure reason
- never print the Discord webhook URL

## Configuration

Environment variables:

- `DISCORD_WEBHOOK_URL` required
- `STATE_FILE` optional, default `seen-products.json`
- `USER_AGENT` optional, default fixed desktop browser string

## Testing

Test coverage should focus on stable behavior rather than live site requests.

Required tests:

- parse fixture HTML for each brand into normalized products
- dedupe logic identifies only unseen products
- first-run baseline does not emit notifications
- Discord payload contains product name, price fallback, image URL, and link
- partial brand failure still processes other brands

Live network tests are out of scope for CI. HTML fixtures should be stored in `tests/fixtures/`.

## GitHub Actions

One workflow:

- scheduled cron `*/5 * * * *`
- optional manual trigger with `workflow_dispatch`
- install dependencies
- run test suite
- run monitor script
- commit updated `seen-products.json` back to the default branch only when it changed

The workflow must avoid printing secrets and should set git author information for automated state commits.

## Security and Operational Notes

- The repository is expected to be public for free GitHub-hosted execution
- Only the Discord webhook URL belongs in secrets
- The pasted webhook in chat must be treated as compromised and replaced before go-live
- Rate limiting should be modest because only three list pages are polled every 5 minutes

## Success Criteria

The first release is successful when:

- a fresh repository can run locally and in GitHub Actions
- the first run writes baseline state without sending Discord messages
- adding an unseen product in a fixture-driven test produces exactly one Discord notification
- the workflow can update and commit `seen-products.json` automatically
