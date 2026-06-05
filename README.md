# Cosme Monitor

Discord notification monitor for new cosmetics arrivals.

The current production setup is `CHANEL only`.

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
.\.venv\Scripts\python -m cosme_monitor
```

## GitHub setup

1. Create a public repository from this directory.
2. Add `DISCORD_WEBHOOK_URL` in repository secrets.
3. Replace any webhook URL that was pasted in chat or logs before going live.
4. Enable GitHub Actions.

The workflow runs every 5 minutes, monitors `CHANEL` only, and commits `seen-products.json` when the state changes.

## Current constraints

- CHANEL works with plain HTTP fetching in current verification.
- Dior may return an anti-bot "Page unavailable" response.
- YSL may return a Cloudflare challenge page.

For production, keep `ENABLED_BRANDS=CHANEL`. Support for other brands remains in the codebase for fixture tests and future non-bypass integrations, but they are not enabled by default.
