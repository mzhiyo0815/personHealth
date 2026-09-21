# Recent Record Prefill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users select one of their five most recent meals or exercises and open a new-record form prefilled with copied content and the current time.

**Architecture:** The today view supplies owner-scoped recent querysets. Existing create routes accept a GET-only `copy` UUID, resolve it through the signed-in user's related manager, and construct `initial` values without copying identity or timestamps. Exercise strength rows are copied into unsaved inline-formset extra forms.

**Tech Stack:** Django 5.2 views/forms/templates, pytest-django, pytest-playwright.

---

### Task 1: Show owner-scoped recent records on today

**Files:**
- Modify: `tracker/views/dashboard.py`
- Modify: `templates/tracker/today.html`
- Test: `tests/tracker/test_dashboard.py`

- [ ] **Step 1: Write failing tests**

Create six meals and six exercises for the signed-in user plus records for another user. Assert `recent_meals` and `recent_exercises` contain five rows in newest-first order, exclude the other user, and render links using `?copy=<uuid>`.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py -q`

Expected: response context lacks both recent-record collections.

- [ ] **Step 3: Implement recent querysets and UI**

Add these owner-scoped slices to the today context:

```python
"recent_meals": request.user.meals.all()[:5],
"recent_exercises": request.user.exercises.all()[:5],
```

Render “最近饮食” and “最近运动” lists with time, type, summary, and a 44×44-compatible “复用” link. Render explicit empty messages when a list is empty.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py -q`

Expected: all dashboard tests pass.

### Task 2: Prefill a new meal securely

**Files:**
- Modify: `tracker/views/records.py`
- Test: `tests/tracker/test_crud.py`
- Test: `tests/tracker/test_isolation.py`

- [ ] **Step 1: Write failing prefill and isolation tests**

Create a meal with every optional nutrition field. GET `/meals/new/?copy=<uuid>` and assert the form initial data copies all allowed content fields while `occurred_at` is current. Assert another user's UUID, a missing UUID, and a malformed UUID return 404. POST the prefilled values and assert a new meal is created while the source remains unchanged.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_crud.py tests/tracker/test_isolation.py -q`

Expected: the copy query is currently ignored and isolation responses are 200.

- [ ] **Step 3: Implement GET-only meal initial data**

Add an owner-scoped UUID resolver that raises `Http404` for malformed, missing, or unowned identifiers. Build meal initial data from an explicit allowlist and set `occurred_at` to `timezone.now()`. Keep POST construction unchanged so submitted values win.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_crud.py tests/tracker/test_isolation.py -q`

Expected: meal copy and isolation tests pass.

### Task 3: Prefill exercise and strength details

**Files:**
- Modify: `tracker/views/records.py`
- Test: `tests/tracker/test_crud.py`
- Test: `tests/tracker/test_isolation.py`

- [ ] **Step 1: Write failing exercise tests**

Create a strength exercise with multiple ordered `StrengthSet` rows. GET `/exercises/new/?copy=<uuid>` and assert the main form initial data, current time, formset total count, row values, order, and lack of child IDs. Assert an unowned or malformed UUID returns 404.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_crud.py tests/tracker/test_isolation.py -q`

Expected: exercise and strength initial values are missing.

- [ ] **Step 3: Implement exercise initial data**

Copy only `exercise_type`, `duration_minutes`, `intensity`, and `notes`, plus current `occurred_at`. Convert source strength rows to dictionaries containing `exercise_name`, `sets`, `reps_per_set`, `load_kg`, and `order`. Set the unsaved formset's `extra` count before forms are evaluated so all copied rows render without IDs.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_crud.py tests/tracker/test_isolation.py -q`

Expected: exercise copy and isolation tests pass.

### Task 4: Browser acceptance and full review

**Files:**
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Add browser acceptance coverage**

Create recent meal and strength exercise data. At 360 pixels, open today, assert both recent sections and links are visible, click each reuse link, verify prefilled values, and assert no document-level horizontal overflow.

- [ ] **Step 2: Run browser tests**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q --browser-channel chrome`

Expected: all browser tests pass.

- [ ] **Step 3: Run complete verification**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest -q -rs --browser-channel chrome && .venv/bin/python manage.py check && git diff --check`

Expected: no failures and no Django or whitespace issues.

- [ ] **Step 4: Request independent review and resolve findings**

Review must cover owner isolation, malformed UUID handling, GET/POST behavior, copied field allowlists, formset counts and child IDs, original-record immutability, and mobile layout. Resolve every Critical and Important finding.

- [ ] **Step 5: Commit and push**

```bash
git add tracker templates tests docs/superpowers/plans/2026-09-21-recent-record-prefill.md
git commit -m "feat: prefill forms from recent records"
git push origin feature/health-app
```
