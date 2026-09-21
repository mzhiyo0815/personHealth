# Trend Summary Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mobile-friendly summary cards to the trends page for measurement changes, weekly-normalized exercise goal progress, and meal-recording completion.

**Architecture:** Pure functions in `tracker.services.trends` calculate presentation-ready summaries from already owner-scoped rows. The trends view separates the selected-range exercise rows from the wider calendar-week query used by the existing weekly table, applies saved or model-default goals without creating database rows, and passes summary dictionaries to the template. CSS provides a responsive card grid without changing existing charts.

**Tech Stack:** Django 5.2, Python `Decimal`, server-rendered HTML/CSS, pytest-django, pytest-playwright.

---

### Task 1: Calculate measurement change summaries

**Files:**
- Modify: `tracker/services/trends.py`
- Test: `tests/tracker/test_trends.py`

- [ ] **Step 1: Write failing measurement-summary tests**

Import `measurement_change_summary` and add tests for empty, one-point, positive, negative, and zero changes:

```python
def test_measurement_change_summary_handles_empty_and_single_point():
    assert measurement_change_summary([]) == {
        "status": "empty", "start": None, "latest": None, "change": None
    }
    assert measurement_change_summary([(date(2026, 9, 21), Decimal("70.20"))]) == {
        "status": "insufficient",
        "start": Decimal("70.20"),
        "latest": Decimal("70.20"),
        "change": None,
    }


@pytest.mark.parametrize(
    ("start", "latest", "expected"),
    (("70.00", "69.50", "-0.50"), ("70.00", "70.40", "0.40"), ("70", "70", "0.00")),
)
def test_measurement_change_summary_calculates_period_delta(start, latest, expected):
    result = measurement_change_summary([
        (date(2026, 9, 20), Decimal(start)),
        (date(2026, 9, 21), Decimal(latest)),
    ])
    assert result["status"] == "ready"
    assert result["change"] == Decimal(expected)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: collection fails because `measurement_change_summary` does not exist.

- [ ] **Step 3: Implement the minimal pure function**

Add to `tracker/services/trends.py`:

```python
def measurement_change_summary(series):
    if not series:
        return {"status": "empty", "start": None, "latest": None, "change": None}
    start = series[0][1]
    latest = series[-1][1]
    if len(series) == 1:
        return {
            "status": "insufficient",
            "start": start,
            "latest": latest,
            "change": None,
        }
    return {
        "status": "ready",
        "start": start,
        "latest": latest,
        "change": (latest - start).quantize(Decimal("0.01")),
    }
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: all trend service and view tests pass.

- [ ] **Step 5: Commit the service change**

```bash
git add tracker/services/trends.py tests/tracker/test_trends.py
git commit -m "feat: calculate measurement trend summaries"
```

### Task 2: Calculate weekly goal and meal-completion summaries

**Files:**
- Modify: `tracker/services/trends.py`
- Test: `tests/tracker/test_trends.py`

- [ ] **Step 1: Write failing goal-progress tests**

Import `weekly_goal_progress` and cover 7-day, 30-day, over-goal, and zero-goal behavior:

```python
def test_weekly_goal_progress_normalizes_selected_range():
    seven_days = weekly_goal_progress(90, 7, 150)
    thirty_days = weekly_goal_progress(300, 30, 150)
    assert seven_days == {
        "status": "ready", "total": 90, "weekly_average": Decimal("90.0"),
        "goal": 150, "percentage": 60, "bar_percentage": 60,
    }
    assert thirty_days["weekly_average"] == Decimal("70.0")
    assert thirty_days["percentage"] == 47


def test_weekly_goal_progress_handles_zero_goal_and_caps_bar():
    assert weekly_goal_progress(14, 7, 0)["status"] == "no_goal"
    result = weekly_goal_progress(300, 7, 150)
    assert result["percentage"] == 200
    assert result["bar_percentage"] == 100
```

- [ ] **Step 2: Write failing meal-summary tests**

Import `meal_completion_summary` and verify duplicate meal types are counted once:

```python
def test_meal_completion_summary_deduplicates_daily_meal_types():
    day = date(2026, 9, 21)
    result = meal_completion_summary(
        [(day, "breakfast"), (day, "breakfast"), (day, "lunch")], 7
    )
    assert result == {
        "completed_slots": 2,
        "total_slots": 28,
        "recorded_days": 1,
        "range_days": 7,
        "percentage": 7,
    }
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: collection fails because both functions are missing.

- [ ] **Step 4: Implement Decimal-safe calculations**

Add `ROUND_HALF_UP` to the decimal import and implement:

```python
def rounded_percentage(numerator, denominator):
    if not denominator:
        return None
    return int(
        (Decimal(numerator) * 100 / Decimal(denominator)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def weekly_goal_progress(total, range_days, weekly_goal):
    weekly_average = (Decimal(total) * 7 / Decimal(range_days)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    percentage = rounded_percentage(weekly_average, weekly_goal)
    return {
        "status": "ready" if percentage is not None else "no_goal",
        "total": total,
        "weekly_average": weekly_average,
        "goal": weekly_goal,
        "percentage": percentage,
        "bar_percentage": min(percentage, 100) if percentage is not None else None,
    }


def meal_completion_summary(rows, range_days):
    completed = set(rows)
    percentage = rounded_percentage(len(completed), range_days * 4)
    return {
        "completed_slots": len(completed),
        "total_slots": range_days * 4,
        "recorded_days": len({day for day, _ in completed}),
        "range_days": range_days,
        "percentage": percentage,
    }
```

- [ ] **Step 5: Run the tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: all trend tests pass.

- [ ] **Step 6: Commit the summary calculators**

```bash
git add tracker/services/trends.py tests/tracker/test_trends.py
git commit -m "feat: calculate habit goal summaries"
```

### Task 3: Connect summaries to owner-scoped trend data

**Files:**
- Modify: `tracker/views/trends.py`
- Test: `tests/tracker/test_trends.py`

- [ ] **Step 1: Write failing integration tests**

Create a saved `UserGoal` and records inside and outside the selected period. Assert the response context contains:

```python
assert response.context["trend_summary"]["exercise"]["total"] == 90
assert response.context["trend_summary"]["exercise"]["goal"] == 180
assert response.context["trend_summary"]["strength"]["total"] == 2
assert response.context["trend_summary"]["meals"]["recorded_days"] == 2
```

Add a separate test with another user's measurements, meals, exercises, and goals. Assert none affect the signed-in user's summary. Add a user-without-saved-goal test asserting defaults of 150 exercise minutes and 2 strength sessions are used without creating a `UserGoal` row.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: `trend_summary` is absent from response context.

- [ ] **Step 3: Assemble summary context in the view**

Move `from datetime import timedelta` to the import block. Import `UserGoal` plus the three new service functions. After building existing series, use:

```python
range_exercise_rows = [row for row in exercise_rows if row[0] >= start_date]
goal = UserGoal.objects.filter(user=request.user).first() or UserGoal()
trend_summary = {
    "weight": measurement_change_summary(weight_series),
    "waist": measurement_change_summary(waist_series),
    "exercise": weekly_goal_progress(
        sum(row[1] for row in range_exercise_rows),
        range_days,
        goal.weekly_exercise_minutes,
    ),
    "strength": weekly_goal_progress(
        sum(row[2] == "strength" for row in range_exercise_rows),
        range_days,
        goal.weekly_strength_sessions,
    ),
    "meals": meal_completion_summary(meal_rows, range_days),
}
```

Add `trend_summary` to the context. Do not save the default `UserGoal` instance.

- [ ] **Step 4: Run integration tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: all trend tests pass, including owner isolation and default-goal behavior.

- [ ] **Step 5: Commit view integration**

```bash
git add tracker/views/trends.py tests/tracker/test_trends.py
git commit -m "feat: connect trend summaries to user data"
```

### Task 4: Render accessible responsive summary cards

**Files:**
- Modify: `templates/tracker/trends.html`
- Modify: `static/css/app.css`
- Modify: `tests/tracker/test_trends.py`
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Write failing template tests**

Create representative data and assert rendered content includes “本期摘要”, “体重变化”, “腰围变化”, “每周平均 90.0 分钟”, “目标 150 分钟”, “力量训练目标”, and “7 天中记录了 2 天”. Add empty and one-point cases that assert “暂无数据” and “至少需要 2 天数据”.

- [ ] **Step 2: Run template tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: summary headings and status messages are absent.

- [ ] **Step 3: Add semantic card markup**

Insert after the range navigation:

```django
<section aria-labelledby="summary-title">
  <h2 id="summary-title">本期摘要</h2>
  <div class="summary-grid">
    <article class="summary-card">
      <h3>体重变化</h3>
      {% if trend_summary.weight.status == "empty" %}<p>暂无数据</p>
      {% elif trend_summary.weight.status == "insufficient" %}
        <strong>{{ trend_summary.weight.latest|floatformat:2 }} 千克（kg）</strong>
        <p>至少需要 2 天数据</p>
      {% else %}
        <strong>{% if trend_summary.weight.change > 0 %}+{% endif %}{{ trend_summary.weight.change|floatformat:2 }} 千克（kg）</strong>
        <p>{{ trend_summary.weight.start|floatformat:2 }} → {{ trend_summary.weight.latest|floatformat:2 }}</p>
      {% endif %}
    </article>
  </div>
</section>
```

Add equivalent waist, exercise, strength, and meal cards. For goals, use semantic `<progress max="100" value="{{ item.bar_percentage }}">` only when status is `ready`; always retain text percentages so the meaning does not depend on color or the progress element.

- [ ] **Step 4: Add responsive card styles**

Add to `static/css/app.css`:

```css
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.summary-card { min-width: 0; padding: 14px; border: 1px solid var(--line); border-radius: 12px; background: var(--bg); }
.summary-card h3 { margin: 0 0 8px; font-size: 1rem; }
.summary-card strong { display: block; font-size: 1.25rem; overflow-wrap: anywhere; }
.summary-card p { margin: 6px 0 0; color: var(--muted); }
.summary-card progress { width: 100%; margin-top: 10px; accent-color: var(--green); }
@media (max-width: 339px) { .summary-grid { grid-template-columns: 1fr; } }
```

- [ ] **Step 5: Run template tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_trends.py -q`

Expected: all summary rendering tests pass.

- [ ] **Step 6: Add browser acceptance coverage**

Extend the supported-width flow to assert `.summary-grid` is visible on `/trends/`. Add a 360-pixel test that switches between `?range=7` and `?range=30`, confirms the summary text changes with range-specific fixtures, and checks:

```python
assert page.evaluate(
    "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
)
assert page.locator(".summary-card").count() == 5
```

- [ ] **Step 7: Run browser and full verification**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q`

Then run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest -q && .venv/bin/python manage.py check && git diff --check`

Expected: no failures, no Django system-check issues, and no whitespace errors.

- [ ] **Step 8: Request independent review and resolve findings**

Review measurement bounds, 7/30-day range isolation, weekly normalization, zero goals, duplicate meals, user isolation, default goals without writes, decimal rounding, factual wording, semantic progress markup, and 360-pixel layout. Resolve every Critical and Important finding.

- [ ] **Step 9: Commit and push**

```bash
git add tracker/services/trends.py tracker/views/trends.py templates/tracker/trends.html static/css/app.css tests/tracker/test_trends.py tests/browser/test_mobile_flows.py docs/superpowers/plans/2026-09-21-trend-summary-cards.md
git commit -m "feat: add trend summary cards"
git push origin feature/health-app
```
