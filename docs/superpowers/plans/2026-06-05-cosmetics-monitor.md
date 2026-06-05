# Cosmetics Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python monitor that checks Dior, CHANEL, and YSL new-arrivals pages, stores seen products, and posts new-product notifications to Discord from GitHub Actions.

**Architecture:** Use a small Python package with separated responsibilities for scraping, normalization, state storage, and Discord delivery. Start with fixture-driven parsers and isolate brand fetch failures so one blocked site does not stop the whole run.

**Tech Stack:** Python 3.12, requests, BeautifulSoup, pytest, GitHub Actions

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/cosme_monitor/__init__.py`

- [ ] Add packaging, dependency, and pytest configuration
- [ ] Add a short README with setup, secrets, and workflow notes

### Task 2: Core models and state

**Files:**
- Create: `src/cosme_monitor/models.py`
- Create: `src/cosme_monitor/state.py`
- Create: `tests/test_state.py`

- [ ] Write failing state tests first
- [ ] Implement normalized product and seen-state handling
- [ ] Run the targeted tests

### Task 3: Brand parsing

**Files:**
- Create: `src/cosme_monitor/brands.py`
- Create: `tests/fixtures/dior_new_arrivals.html`
- Create: `tests/fixtures/chanel_new_arrivals.html`
- Create: `tests/fixtures/ysl_new_arrivals.html`
- Create: `tests/test_brands.py`

- [ ] Write failing parser tests for Dior, CHANEL, and YSL fixtures
- [ ] Implement brand parsers and fetch wrappers
- [ ] Run the targeted tests

### Task 4: Discord notifications and orchestration

**Files:**
- Create: `src/cosme_monitor/discord.py`
- Create: `src/cosme_monitor/monitor.py`
- Create: `tests/test_monitor.py`

- [ ] Write failing tests for first-run baseline, unseen detection, and Discord payload generation
- [ ] Implement monitor orchestration and webhook delivery
- [ ] Run the targeted tests

### Task 5: CLI and automation

**Files:**
- Create: `src/cosme_monitor/__main__.py`
- Create: `.github/workflows/monitor.yml`

- [ ] Add CLI entrypoint
- [ ] Add scheduled GitHub Actions workflow with state commit step
- [ ] Run the full test suite
