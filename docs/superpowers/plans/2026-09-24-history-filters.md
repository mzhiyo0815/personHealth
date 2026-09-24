# History Record Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe, mobile-friendly date-range, record-type, and keyword filters to the history page while preserving owner isolation and day pagination.

**Architecture:** A typed Django `HistoryFilterForm` validates all GET input. The history view applies cleaned values independently to owner-scoped querysets, builds the union of matching local dates in the database, and exposes a canonical query string for pagination. The existing server-rendered template and CSS provide a no-JavaScript mobile interface.

**Tech Stack:** Django 5.2 forms and ORM, PostgreSQL/SQLite-compatible queries, pytest-django, pytest-playwright, HTML/CSS.

---

## File map

- Modify `tracker/forms.py` — define and validate the history filter contract.
- Modify `tracker/views/history.py` — apply cleaned filters, retain database day pagination, and build canonical pagination parameters.
- Modify `templates/tracker/history.html` — render filters, errors, result state, and preserved pagination links.
- Modify `static/css/app.css` — responsive filter and pagination layout.
- Modify `tests/tracker/test_dashboard.py` — form, query, isolation, boundary, and pagination tests.
- Modify `tests/browser/test_mobile_flows.py` — supported-width interaction and overflow tests.

### Task 1: Add the typed history filter form

**Files:**
- Modify: `tracker/forms.py`
- Test: `tests/tracker/test_dashboard.py`

- [ ] **Step 1: Write failing form validation tests**

Add tests that instantiate `HistoryFilterForm` and assert:

```python
def test_history_filter_rejects_reversed_dates():
    form = HistoryFilterForm({"start_date": "2026-09-20", "end_date": "2026-09-19"})
    assert not form.is_valid()
    assert form.non_field_errors() == ["开始日期不能晚于结束日期。"]


def test_history_filter_rejects_unknown_type_and_long_keyword():
    assert not HistoryFilterForm({"record_type": "unknown"}).is_valid()
    assert not HistoryFilterForm({"keyword": "食" * 101}).is_valid()
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py -k history_filter -q`

Expected: collection fails because `HistoryFilterForm` does not exist.

- [ ] **Step 3: Implement the minimal form**

In `tracker/forms.py`, add a `forms.Form` with optional `start_date`, `end_date`, `record_type`, and `keyword` fields. Use `DateInput(attrs={"type": "date"})`, a `ChoiceField` with `all`, `meal`, `exercise`, `weight`, and `waist`, and `CharField(max_length=100)`. In `clean()`, raise `forms.ValidationError("开始日期不能晚于结束日期。")` when both dates exist in reverse order.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py -k history_filter -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add tracker/forms.py tests/tracker/test_dashboard.py
git commit -m "feat: validate history filters"
```

### Task 2: Apply owner-scoped filters and preserve pagination

**Files:**
- Modify: `tracker/views/history.py`
- Test: `tests/tracker/test_dashboard.py`

- [ ] **Step 1: Write failing query behavior tests**

Create records on and outside the requested range for both users, then cover:

```python
response = client.get("/history/", {
    "start_date": "2026-09-18",
    "end_date": "2026-09-20",
    "record_type": "meal",
    "keyword": "鸡蛋",
})
assert "自己的鸡蛋早餐" in response.content.decode()
assert "自己的跑步" not in response.content.decode()
assert "他人的鸡蛋早餐" not in response.content.decode()
```

Also test local start/end-day inclusion, meal `food` and `portion` matching, exercise `notes` matching, keyword plus measurement returning empty, invalid form returning no records, and a page-two link containing all URL-encoded valid filters.

- [ ] **Step 2: Run query tests and confirm failure**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py -k 'history and (range or type or keyword or pagination)' -q`

Expected: new assertions fail because the view ignores the new parameters.

- [ ] **Step 3: Refactor the history view around cleaned querysets**

Replace `parse_date()` and the legacy `date` parameter with `HistoryFilterForm(request.GET)`. When valid:

```python
filters = form.cleaned_data
querysets = {
    "meal": request.user.meals.all(),
    "exercise": request.user.exercises.all(),
    "measurement": request.user.measurements.all(),
}
```

Apply `occurred_at__gte` using `local_day_bounds(start_date)[0]` and `occurred_at__lt` using `local_day_bounds(end_date)[1]`. Select only the requested record queryset; split measurement type into `kind="weight"` or `kind="waist"`. Apply keyword with `Q(food__icontains=keyword) | Q(portion__icontains=keyword)` for meals and `Q(notes__icontains=keyword)` for exercises; exclude measurement querysets whenever keyword is non-empty.

Build the existing `TruncDate` union from only the filtered querysets. If the form is invalid, use an empty list as the day source. Continue retrieving only the current page's date window and filter its records through those same querysets.

Build pagination parameters from a copy of `request.GET`, remove `page`, and expose `filter_query = params.urlencode()`. Expose `has_filters` from non-empty cleaned values and `filter_valid=form.is_valid()`.

- [ ] **Step 4: Run dashboard and isolation tests**

Run: `.venv/bin/pytest tests/tracker/test_dashboard.py tests/tracker/test_isolation.py -q`

Expected: all tests pass, including database `UNION ... LIMIT 7` coverage for the unfiltered path.

- [ ] **Step 5: Commit**

```bash
git add tracker/views/history.py tests/tracker/test_dashboard.py
git commit -m "feat: filter owner history records"
```

### Task 3: Render responsive filters and complete acceptance

**Files:**
- Modify: `templates/tracker/history.html`
- Modify: `static/css/app.css`
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Write failing template and browser tests**

Assert the response contains Chinese labels “开始日期”, “结束日期”, “记录类型”, and “关键词”; invalid input renders the expected Chinese error and no records; active filters show “清除筛选”; empty filtered results show “没有符合筛选条件的记录。”.

Add a Playwright test parameterized at 360, 390, 430, and 1280 pixels that submits a combined filter, verifies only the matching record is visible, asserts every input/button/link has at least 44px touch height where applicable, and checks `document.documentElement.scrollWidth <= document.documentElement.clientWidth`.

- [ ] **Step 2: Run the new tests and confirm failure**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -k history_filters -q`

Expected: tests fail because the new controls and result states are absent.

- [ ] **Step 3: Implement the server-rendered interface**

Render `{{ filter_form }}` fields explicitly inside `.history-filters`, including non-field and field errors. Add submit and clear controls. Use:

```django
{% if filter_form.errors %}
  <p>请修正筛选条件。</p>
{% elif not page.object_list and has_filters %}
  <p>没有符合筛选条件的记录。</p>
{% elif not page.object_list %}
  <p>暂无记录。</p>
{% endif %}
```

For pagination, append `&{{ filter_query }}` only when non-empty, and show `第 {{ page.number }} / {{ page.paginator.num_pages }} 页`. In CSS, keep one column by default and use a two-column `.history-filter-grid` at 720px, with full-width actions and no horizontal overflow.

- [ ] **Step 4: Run complete verification**

Run:

```bash
DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest -q
.venv/bin/python manage.py check
git diff --check
```

Expected: all tests pass, Django reports no issues, and the diff check is clean.

- [ ] **Step 5: Request code review and fix findings**

Ask the existing reviewer to inspect owner isolation, invalid-filter behavior, timezone boundaries, query count/pagination semantics, template escaping, and mobile accessibility. Resolve every Critical or Important finding, then rerun Step 4.

- [ ] **Step 6: Commit and push**

```bash
git add templates/tracker/history.html static/css/app.css tests/browser/test_mobile_flows.py
git commit -m "feat: add responsive history filters"
git push origin feature/health-app
```
