# CHANEL Article Monitoring Design

Date: 2026-06-07

## Goal

Add `CHANEL` to the existing article monitoring pipeline so Discord can receive new article alerts from the same public sources already used for `Dior` and `YSL`.

## Scope

- Reuse the current `PR TIMES` integration pattern
- Reuse the current `FASHIONSNAP` beauty-news parsing flow
- Add `CHANEL` brand matching and configuration defaults
- Update tests and operator-facing documentation

## Non-Goals

- Adding new media sources
- Changing Discord payload structure
- Reworking product monitoring

## Design

1. Extend `PRTIMES_SOURCES` with the `CHANEL` company mapping.
2. Extend `FASHIONSNAP_KEYWORDS` with `CHANEL` and Japanese keyword variants.
3. Update runtime defaults so article monitoring can include `CHANEL`.
4. Keep the existing article filtering and deduping behavior unchanged.
5. Update tests to cover `CHANEL` parsing and default configuration behavior.

## Validation

- `python -m pytest -q`
- `python -m cosme_monitor` with article brands including `CHANEL`
