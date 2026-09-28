# History Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show complete saved meal and exercise information inline on the history page.

**Architecture:** Extend the existing server-rendered history rows with native details elements. Prefetch strength rows only for the current page's exercise queryset. Keep all data owner-scoped.

**Tech Stack:** Django 5.2 ORM and templates, pytest-django, pytest-playwright, CSS.

---

### Task 1: Detail content and isolation

**Files:** `templates/tracker/history.html`, `tests/tracker/test_dashboard.py`

- [ ] Write failing tests with a meal containing every optional value, a blank meal, a strength exercise with two ordered actions, and another user's strength exercise. Assert Chinese labels and units, zero values, action order, empty-state wording, and absence of other user's data.
- [ ] Run `.venv/bin/pytest tests/tracker/test_dashboard.py -k history_detail -q`; verify failures are due to missing detail content.
- [ ] Add `<details class="history-detail"><summary>查看详情</summary>...</details>` to meal and exercise rows. Use explicit `{% if value != None %}` for nullable decimal/numeric values so zero remains visible, and omit empty strings.
- [ ] Run the focused tests, then all dashboard tests; fix any regressions.

### Task 2: Prefetch and mobile acceptance

**Files:** `tracker/views/history.py`, `static/css/app.css`, `tests/tracker/test_dashboard.py`, `tests/browser/test_mobile_flows.py`

- [ ] Write a failing query-count test comparing one versus several exercises with strength rows, and a browser test that expands a detail at 360/390/430/1280px, verifies visible content, minimum 44px summary height, and no horizontal overflow.
- [ ] Run targeted tests to observe the query-count/browser failure.
- [ ] Add `prefetch_related("strength_sets")` only to the exercise queryset used to fetch the current page's records. Style `.history-detail` with wrapping and a 44px summary touch area.
- [ ] Run `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest -q`, `.venv/bin/python manage.py check`, and `git diff --check`. Review owner isolation, query count, escaping, and empty/zero handling.
- [ ] Commit `feat: show health record details in history` and push `feature/health-app`.
