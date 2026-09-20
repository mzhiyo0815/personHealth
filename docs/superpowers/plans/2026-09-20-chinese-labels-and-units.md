# Chinese Labels and Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace user-visible English labels with Chinese and show explicit units wherever health values appear.

**Architecture:** Keep database fields and export schemas stable. Localize at the Django form layer, localize Django password forms through small subclasses, and render type-specific units in templates and existing chart payloads.

**Tech Stack:** Django 5.2 forms/templates, pytest-django, pytest-playwright.

---

### Task 1: Localize account and health forms

**Files:**
- Modify: `accounts/forms.py`
- Modify: `tracker/forms.py`
- Modify: `tracker/views/profile.py`
- Test: `tests/accounts/test_auth.py`
- Test: `tests/tracker/test_crud.py`

- [ ] **Step 1: Write failing label tests**

Add assertions for registration passwords, login password, meal, exercise, strength, measurement, goal, and password-change labels. Expected labels include `密码`, `确认密码`, `记录时间`, `热量（千卡 kcal）`, `运动时长（分钟）`, `负重（千克 kg）`, and `数值（体重 kg，腰围 cm）`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv/bin/pytest tests/accounts/test_auth.py tests/tracker/test_crud.py -q`

Expected: failures show current English model-derived labels such as `Occurred at`, `Meal type`, and `Password confirmation`.

- [ ] **Step 3: Add explicit form labels**

Set `labels` in each `ModelForm.Meta`, set `DELETE` to `删除本条`, and add Chinese labels/help text to authentication and password-change forms. Use a localized `PasswordChangeForm` subclass from `UserPasswordChangeView.form_class`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/accounts/test_auth.py tests/tracker/test_crud.py -q`

Expected: all focused tests pass.

### Task 2: Add units to history, trends, and profile links

**Files:**
- Modify: `templates/tracker/history.html`
- Modify: `templates/tracker/profile.html`
- Modify: `tracker/views/trends.py`
- Test: `tests/tracker/test_dashboard.py`
- Test: `tests/tracker/test_trends.py`

- [ ] **Step 1: Write failing rendering tests**

Create weight, waist, exercise, and nutrition data. Assert history includes `分钟`, `千克（kg）`, and `厘米（cm）`; trend tables include `千克（kg）`, `厘米（cm）`, `千卡（kcal）`, and `克（g）`; profile links include `导出完整数据（JSON）` and `导出表格数据（CSV）`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py tests/tracker/test_trends.py tests/tracker/test_export.py -q`

Expected: unit and export-link assertions fail.

- [ ] **Step 3: Render exact units**

Use `record.kind` to select `千克（kg）` or `厘米（cm）` in history. Change chart payload units to the same Chinese-first notation and update the two export links without changing endpoints or exported field names.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py tests/tracker/test_trends.py tests/tracker/test_export.py -q`

Expected: all focused tests pass.

### Task 3: Browser-check visible Chinese labels

**Files:**
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Add a failing browser test**

Visit registration, meal, exercise, measurement, profile, and password-change pages. Assert expected Chinese labels and unit text are visible and known English labels are absent.

- [ ] **Step 2: Run the browser test and verify RED or expose missed labels**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q --browser-channel chrome`

Expected: any remaining default English label is reported.

- [ ] **Step 3: Fix only missed user-visible labels**

Update the responsible form or template while leaving HTML field names and API/export schemas unchanged.

- [ ] **Step 4: Run browser tests and verify GREEN**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q --browser-channel chrome`

Expected: all browser tests pass at supported widths.

### Task 4: Full verification and review

**Files:**
- Review all files changed above.

- [ ] **Step 1: Run all tests**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest -q -rs --browser-channel chrome`

Expected: no failures; only the existing date-conditional trend test may skip.

- [ ] **Step 2: Run Django and diff checks**

Run: `.venv/bin/python manage.py check && git diff --check`

Expected: no issues and no whitespace errors.

- [ ] **Step 3: Request independent code review**

Review for untranslated visible labels, missing or incorrect units, schema changes, and regressions. Resolve all Critical and Important findings.

- [ ] **Step 4: Commit and push**

```bash
git add accounts tracker templates tests docs/superpowers/plans/2026-09-20-chinese-labels-and-units.md
git commit -m "feat: localize labels and show health units"
git push origin feature/health-app
```
