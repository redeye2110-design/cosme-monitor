# Cosme Monitor

Discord notification monitor for cosmetics launches.

The current production setup is:

- `CHANEL` product new-arrivals monitoring
- `CHANEL` article monitoring via `PR TIMES` and `FASHIONSNAP`
- `Dior` product new-arrivals monitoring
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
$env:ENABLED_BRANDS="CHANEL,Dior,YSL"
$env:ENABLED_ARTICLE_BRANDS="DIOR,YSL,CHANEL"
.\.venv\Scripts\python -m cosme_monitor
```

## GitHub setup

1. Create a public repository from this directory.
2. Add `DISCORD_WEBHOOK_URL` in repository secrets.
3. Replace any webhook URL that was pasted in chat or logs before going live.
4. Enable GitHub Actions.

The workflow runs every 5 minutes and commits `seen-products.json` when the state changes.

Default production env:

- `ENABLED_BRANDS=CHANEL,Dior,YSL`
- `ENABLED_ARTICLE_BRANDS=DIOR,YSL,CHANEL`

## Current constraints

- CHANEL product monitoring works with plain HTTP fetching in current verification.
- Dior product monitoring currently works through browser automation in local verification.
- YSL product pages may still return anti-bot or challenge responses.
- CHANEL, Dior, and YSL article monitoring uses public PR TIMES API responses and FASHIONSNAP beauty news HTML.

Current production defaults match the workflow file and monitor CHANEL and Dior products plus CHANEL, Dior, and YSL articles.
