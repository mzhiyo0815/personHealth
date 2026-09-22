# Previous Period Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare the selected 7-day or 30-day trend period with the immediately preceding equal-length period for measurements, exercise, strength sessions, and meal-recording completion.

**Architecture:** Pure service functions produce comparison dictionaries without database access. The trends view expands each owner-scoped query to the previous-period start, partitions rows by local date, preserves current-only inputs for existing charts and summaries, and passes a five-item comparison payload to the template. Server-rendered semantic HTML and responsive CSS present factual deltas without value-judgment colors.

**Tech Stack:** Django 5.2, Python `Decimal`, server-rendered HTML/CSS, pytest-django, pytest-playwright.

---

### Task 1: Add pure comparison calculators

**Files:**
- Modify: `tracker/services/trends.py`
- Test: `tests/tracker/test_trends.py`

- [ ] **Step 1: Write failing measurement comparison tests**

Import `latest_value_comparison` and add:

```python
def test_latest_value_comparison_uses_each_period_latest_value():
    previous = [
        (date(2026, 9, 7), Decimal("71.00")),
        (date(2026, 9, 14), Decimal("70.50")),
    ]
    current = [
        (date(2026, 9, 15), Decimal("70.20")),
        (date(2026, 9, 21), Decimal("69.80")),
    ]
    assert latest_value_comparison(current, previous) == {
        "status": "ready",
        "current": Decimal("69.80"),
        "previous": Decimal("70.50"),
        "change": Decimal("-0.70"),
    }


@pytest.mark.parametrize(("current", "previous"), (([], []), ([(date(2026, 9, 21), Decimal("70"))], []), ([], [(date(2026, 9, 14), Decimal("70"))])))
def test_latest_value_comparison_requires_both_periods(current, previous):
    assert latest_value_comparison(current, previous)["status"] == "insufficient"
```

- [ ] **Step 2: Write failing general numeric comparison tests**

Import `numeric_comparison` and add:

```python
def test_numeric_comparison_handles_integer_and_decimal_values():
    assert numeric_comparison(90, 60) == {
        "current": 90, "previous": 60, "change": 30
    }
    assert numeric_comparison(7, 14) == {
        "current": 7, "previous": 14, "change": -7
    }
    assert numeric_comparison(Decimal("12.345"), Decimal("10.001"), Decimal("0.01")) == {
        "current": Decimal("12.35"),
        "previous": Decimal("10.00"),
        "change": Decimal("2.34"),
    }
```

- [ ] **Step 3: Run trend tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: collection fails because `latest_value_comparison` and `numeric_comparison` do not exist.

- [ ] **Step 4: Implement the minimal pure functions**

Add to `tracker/services/trends.py`:

```python
def numeric_comparison(current, previous, quantum=None):
    if quantum is None:
        return {"current": current, "previous": previous, "change": current - previous}
    current_value = Decimal(current).quantize(quantum, rounding=ROUND_HALF_UP)
    previous_value = Decimal(previous).quantize(quantum, rounding=ROUND_HALF_UP)
    return {
        "current": current_value,
        "previous": previous_value,
        "change": (current_value - previous_value).quantize(
            quantum, rounding=ROUND_HALF_UP
        ),
    }


def latest_value_comparison(current_series, previous_series):
    if not current_series or not previous_series:
        return {
            "status": "insufficient",
            "current": current_series[-1][1] if current_series else None,
            "previous": previous_series[-1][1] if previous_series else None,
            "change": None,
        }
    comparison = numeric_comparison(
        current_series[-1][1], previous_series[-1][1], Decimal("0.01")
    )
    return {"status": "ready", **comparison}
```

- [ ] **Step 5: Run trend tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: all trend tests pass.

- [ ] **Step 6: Commit the calculators**

```bash
git add tracker/services/trends.py tests/tracker/test_trends.py
git commit -m "feat: calculate previous period comparisons"
```

### Task 2: Partition owner-scoped trend rows into equal periods

**Files:**
- Modify: `tracker/views/trends.py`
- Test: `tests/tracker/test_trends.py`

- [ ] **Step 1: Write failing integration and boundary tests**

Add a helper in the test file for local noon timestamps:

```python
def local_noon(day):
    return timezone.make_aware(
        datetime.combine(day, time(12, 0)), timezone.get_current_timezone()
    )
```

Create records on `previous_start_date`, `current_start_date`, and one day before `previous_start_date`. Assert for `range=7`:

```python
comparison = response.context["period_comparison"]
assert comparison["label"] == "较前 7 天"
assert comparison["exercise"] == {"current": 90, "previous": 60, "change": 30}
assert comparison["strength"] == {"current": 2, "previous": 1, "change": 1}
assert comparison["meals"]["current"] == 7
assert comparison["meals"]["previous"] == 4
assert response.context["trend_summary"]["exercise"]["total"] == 90
```

The record before `previous_start_date` must affect none of these values. Add `range=30` coverage with a record 20 days ago that is in the current 30 days but outside the current 7 days.

- [ ] **Step 2: Write failing measurement and owner-isolation tests**

Create previous/current weight and waist records, plus large values for another user. Assert current-minus-previous values use only the signed-in user. Add a missing-current or missing-previous case and assert `status == "insufficient"`.

- [ ] **Step 3: Run focused tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: `period_comparison` is absent from response context.

- [ ] **Step 4: Expand and partition measurement rows**

In `tracker/views/trends.py`, compute:

```python
previous_start_date = start_date - timedelta(days=range_days)
previous_start, _ = local_day_bounds(previous_start_date)
```

Query measurements from `previous_start` through `end`. Partition each row by local date:

```python
current_measurement_rows = {Measurement.Kind.WEIGHT: [], Measurement.Kind.WAIST: []}
previous_measurement_rows = {Measurement.Kind.WEIGHT: [], Measurement.Kind.WAIST: []}
for item in measurements:
    day = timezone.localtime(item.occurred_at).date()
    row = (day, item.value)
    if day >= start_date:
        current_measurement_rows[item.kind].append(row)
    else:
        previous_measurement_rows[item.kind].append(row)
```

Apply `latest_daily_values` to each list. Keep `weight_series` and `waist_series` assigned from current-period lists so existing charts remain unchanged.

- [ ] **Step 5: Expand and partition exercise and meal rows**

Query exercises from the earlier of `previous_start` and the existing calendar-week start. Partition into `current_exercise_rows`, `previous_exercise_rows`, and `weekly_exercise_rows`. Use only `current_exercise_rows` for `trend_summary`, and only `weekly_exercise_rows` for the existing weekly table.

Query meals from `previous_start`. Build `current_meal_rows`, `previous_meal_rows`, and current-only `nutrition_rows`. Use only current rows for the existing daily completion table and nutrition charts.

- [ ] **Step 6: Assemble comparison context**

Import `latest_value_comparison` and `numeric_comparison`. Calculate:

```python
current_meal_summary = meal_completion_summary(current_meal_rows, range_days)
previous_meal_summary = meal_completion_summary(previous_meal_rows, range_days)
period_comparison = {
    "label": f"较前 {range_days} 天",
    "weight": latest_value_comparison(weight_series, previous_weight_series),
    "waist": latest_value_comparison(waist_series, previous_waist_series),
    "exercise": numeric_comparison(
        sum(row[1] for row in current_exercise_rows),
        sum(row[1] for row in previous_exercise_rows),
    ),
    "strength": numeric_comparison(
        sum(row[2] == "strength" for row in current_exercise_rows),
        sum(row[2] == "strength" for row in previous_exercise_rows),
    ),
    "meals": numeric_comparison(
        current_meal_summary["percentage"], previous_meal_summary["percentage"]
    ),
}
```

Add `period_comparison` to context. Reuse `current_meal_summary` in `trend_summary` rather than recalculating it.

- [ ] **Step 7: Run integration tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: all service, range-boundary, owner-isolation, and existing trend tests pass.

- [ ] **Step 8: Commit view integration**

```bash
git add tracker/views/trends.py tests/tracker/test_trends.py
git commit -m "feat: compare equal trend periods"
```

### Task 3: Render responsive factual comparisons

**Files:**
- Modify: `templates/tracker/trends.html`
- Modify: `static/css/app.css`
- Modify: `tests/tracker/test_trends.py`
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Write failing template tests**

Create representative current/previous data and assert rendered HTML includes:

```python
assert "较前 7 天" in content
assert "体重" in content
assert "-0.70 千克（kg）" in content
assert "+30 分钟" in content
assert "+1 次" in content
assert "+3 个百分点" in content
assert "当前 90 / 上期 60" in content
```

Add a missing-measurement-period test asserting the corresponding item contains “数据不足”.

- [ ] **Step 2: Run template tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: comparison heading and values are absent.

- [ ] **Step 3: Add semantic comparison markup**

Insert after the existing summary section:

```django
<section aria-labelledby="comparison-title">
  <h2 id="comparison-title">{{ period_comparison.label }}</h2>
  <div class="comparison-grid">
    <article class="comparison-item">
      <h3>体重</h3>
      {% if period_comparison.weight.status == "ready" %}
        <strong>{% if period_comparison.weight.change > 0 %}+{% endif %}{{ period_comparison.weight.change|floatformat:2 }} 千克（kg）</strong>
        <p>当前 {{ period_comparison.weight.current|floatformat:2 }} / 上期 {{ period_comparison.weight.previous|floatformat:2 }}</p>
      {% else %}<p>数据不足</p>{% endif %}
    </article>
  </div>
</section>
```

Add equivalent waist, exercise, strength, and meal items. Exercise and strength display integer deltas with explicit `+` for positive values. Meal difference uses “个百分点”. Do not assign positive or negative semantic colors.

- [ ] **Step 4: Add responsive styles**

Add to `static/css/app.css`:

```css
.comparison-grid { display: grid; gap: 10px; }
.comparison-item { min-width: 0; padding: 12px 0; border-bottom: 1px solid var(--line); }
.comparison-item:last-child { border-bottom: 0; }
.comparison-item h3, .comparison-item p { margin: 0; }
.comparison-item strong { display: block; margin: 4px 0; font-size: 1.15rem; overflow-wrap: anywhere; }
.comparison-item p { color: var(--muted); }
@media (min-width: 720px) { .comparison-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 24px; } }
```

- [ ] **Step 5: Run template tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: all trend rendering tests pass.

- [ ] **Step 6: Add browser acceptance**

At 360 pixels, create records that produce different 7-day and 30-day comparisons. Switch the range link and assert the heading changes from “较前 7 天” to “较前 30 天”, comparison text updates, five `.comparison-item` elements remain visible, and:

```python
assert page.evaluate(
    "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
)
```

Extend the existing multi-width trend check to assert `.comparison-grid` is visible at 360, 390, 430, and 1280 pixels.

- [ ] **Step 7: Run browser and full verification**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q`

Then run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest -q && .venv/bin/python manage.py check && git diff --check`

Expected: no test failures, no Django system-check issues, and no whitespace errors.

- [ ] **Step 8: Request independent review and resolve findings**

Review local-date boundaries, equal non-overlapping periods, daily latest-value rules, current-only chart inputs, weekly-table isolation, nutrition isolation, meal deduplication, owner scoping, factual wording, and mobile overflow. Resolve every Critical and Important finding.

- [ ] **Step 9: Commit and push**

```bash
git add tracker/services/trends.py tracker/views/trends.py templates/tracker/trends.html static/css/app.css tests/tracker/test_trends.py tests/browser/test_mobile_flows.py docs/superpowers/plans/2026-09-22-previous-period-comparison.md
git commit -m "feat: compare health trends with previous period"
git push origin feature/health-app
```
