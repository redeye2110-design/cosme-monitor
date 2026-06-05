# Cosme Monitor

Discord notification monitor for cosmetics launches.

The current production setup is:

- `CHANEL` product new-arrivals monitoring
- `Dior` article monitoring via `PR TIMES` and `FASHIONSNAP`
- `YSL` article monitoring via `PR TIMES` and `FASHIONSNAP`

## Stack

- Python 3.12+
- GitHub Actions
- Discord Webhook

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
```

Set the webhook and run:

```powershell
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
$env:ENABLED_BRANDS="CHANEL"
$env:ENABLED_ARTICLE_BRANDS="DIOR,YSL"
.\.venv\Scripts\python -m cosme_monitor
```

## GitHub setup

1. Create a public repository from this directory.
2. Add `DISCORD_WEBHOOK_URL` in repository secrets.
3. Replace any webhook URL that was pasted in chat or logs before going live.
4. Enable GitHub Actions.

The workflow runs every 5 minutes and commits `seen-products.json` when the state changes.

Default production env:

- `ENABLED_BRANDS=CHANEL`
- `ENABLED_ARTICLE_BRANDS=DIOR,YSL`

## Current constraints

- CHANEL product monitoring works with plain HTTP fetching in current verification.
- Dior and YSL product pages may return anti-bot or challenge responses.
- Dior and YSL article monitoring uses public PR TIMES API responses and FASHIONSNAP beauty news HTML.

For production, keep `ENABLED_BRANDS=CHANEL` and use article monitoring for `Dior` and `YSL`.
