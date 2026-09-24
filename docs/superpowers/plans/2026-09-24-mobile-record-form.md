# Mobile Record Form Progressive Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make mobile record forms shorter and easier to operate by progressively disclosing optional fields, supporting dynamic strength rows, preserving those rows in drafts, and improving mobile input controls.

**Architecture:** Django forms and views provide typed form context, server-rendered fallback rows, field errors, and secure formset management. `record-form.js` owns only progressive disclosure and inline-formset DOM operations, while `draft-form.js` owns persistence and asks the record-form API to create enough rows before restoring field values. Templates use small reusable field and strength-row partials; all security and final-count rules remain server-side.

**Tech Stack:** Django 5.2 forms/views/templates, native JavaScript, responsive CSS, pytest-django, pytest-playwright.

---

### Task 1: Add typed record-form sections and mobile input hints

**Files:**
- Modify: `tracker/forms.py`
- Modify: `tracker/views/records.py`
- Modify: `templates/tracker/record_form.html`
- Create: `templates/tracker/components/form_field.html`
- Create: `templates/tracker/components/strength_row.html`
- Test: `tests/tracker/test_crud.py`
- Test: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Write failing input-mode tests**

Extend the form widget test in `tests/tracker/test_crud.py`:

```python
def test_record_number_fields_use_mobile_input_modes():
    assert MealForm().fields["fullness"].widget.attrs["inputmode"] == "numeric"
    for field in ("calories", "protein", "carbohydrates", "fat"):
        assert MealForm().fields[field].widget.attrs["inputmode"] == "decimal"
    assert ExerciseForm().fields["duration_minutes"].widget.attrs["inputmode"] == "numeric"
    assert StrengthSetForm().fields["sets"].widget.attrs["inputmode"] == "numeric"
    assert StrengthSetForm().fields["reps_per_set"].widget.attrs["inputmode"] == "numeric"
    assert StrengthSetForm().fields["load_kg"].widget.attrs["inputmode"] == "decimal"
    assert MeasurementForm().fields["value"].widget.attrs["inputmode"] == "decimal"
```

- [ ] **Step 2: Write failing typed-context and section tests**

Add tests that GET meal, exercise, and measurement create pages and assert:

```python
assert meal_response.context["form_kind"] == "meal"
assert exercise_response.context["form_kind"] == "exercise"
assert measurement_response.context["form_kind"] == "measurement"
assert 'data-optional-section="nutrition"' in meal_response.content.decode()
assert 'data-strength-formset="strength_sets"' in exercise_response.content.decode()
assert 'data-formset-template' in exercise_response.content.decode()
assert "__prefix__" in exercise_response.content.decode()
```

Create a meal copy with calories and assert the nutrition `<details>` has `open`. POST invalid nutrition and assert it remains open with the field error. Create a strength exercise and assert its edit page opens strength details. Assert a normal walking create form leaves it closed.

- [ ] **Step 3: Run focused tests and verify RED**

Run: `.venv/bin/pytest tests/tracker/test_crud.py tests/browser/test_mobile_flows.py::test_record_form_enables_non_sensitive_draft_recovery -q`

Expected: input modes, `form_kind`, and structured-section markers are absent.

- [ ] **Step 4: Add mobile input-mode attributes**

Update widgets in `tracker/forms.py`:

```python
"fullness": forms.NumberInput(attrs={"min": 1, "max": 10, "inputmode": "numeric"}),
"calories": forms.NumberInput(attrs={"min": 0, "step": "0.01", "inputmode": "decimal"}),
"duration_minutes": forms.NumberInput(attrs={"min": 1, "max": 1440, "inputmode": "numeric"}),
"sets": forms.NumberInput(attrs={"min": 1, "inputmode": "numeric"}),
"reps_per_set": forms.NumberInput(attrs={"min": 1, "inputmode": "numeric"}),
"load_kg": forms.NumberInput(attrs={"min": 0, "step": "0.01", "inputmode": "decimal"}),
"value": forms.NumberInput(attrs={"min": 0.01, "step": "0.01", "inputmode": "decimal"}),
```

Apply `inputmode="decimal"` to protein, carbohydrates, and fat as well.

- [ ] **Step 5: Add a shared record context helper**

In `tracker/views/records.py`, add explicit field sets and helpers:

```python
NUTRITION_FIELDS = ("calories", "protein", "carbohydrates", "fat")
STRENGTH_CONTENT_FIELDS = ("exercise_name", "sets", "reps_per_set", "load_kg")


def form_fields_have_content(form, field_names):
    return any(
        form[name].value() not in (None, "") or bool(form[name].errors)
        for name in field_names
    )


def record_form_context(form, title, form_kind, formset=None):
    context = {"form": form, "title": title, "form_kind": form_kind}
    if form_kind == "meal":
        context["nutrition_open"] = form_fields_have_content(form, NUTRITION_FIELDS)
    if formset is not None:
        context["formset"] = formset
        context["strength_open"] = (
            form["exercise_type"].value() == "strength"
            or bool(formset.non_form_errors())
            or any(
                child.errors
                or form_fields_have_content(child, STRENGTH_CONTENT_FIELDS)
                for child in formset.forms
            )
        )
    return context
```

Replace every record-form render context with this helper and the stable kind: meal create/edit use `meal`, exercise create/edit use `exercise`, and measurement create/edit use `measurement`.

- [ ] **Step 6: Create reusable field and strength-row partials**

Create `templates/tracker/components/form_field.html`:

```django
<p{% if field.errors %} class="field-with-errors"{% endif %}>
  {{ field.label_tag }}
  {{ field }}
  {% if field.help_text %}<span class="helptext">{{ field.help_text }}</span>{% endif %}
  {{ field.errors }}
</p>
```

Create `templates/tracker/components/strength_row.html`:

```django
<fieldset class="strength-row" data-formset-row>
  <legend>动作 <span data-row-number>{{ row_number }}</span></legend>
  {% for hidden in strength_form.hidden_fields %}{{ hidden }}{% endfor %}
  {% for field in strength_form.visible_fields %}
    {% if field.name == "DELETE" %}<span hidden>{{ field }}</span>
    {% else %}{% include "tracker/components/form_field.html" with field=field %}{% endif %}
  {% endfor %}
  <button type="button" class="secondary-button" data-remove-row>删除本条</button>
</fieldset>
```

- [ ] **Step 7: Render typed sections with a no-JavaScript fallback**

Replace `record_form.html` with explicit branches. Always render `form.non_field_errors` and hidden fields. For meals, render the five base fields and nutrition fields inside:

```django
<details data-optional-section="nutrition"{% if nutrition_open %} open{% endif %}>
  <summary>可选营养信息</summary>
  {% for field in form.visible_fields %}
    {% if field.name == "calories" or field.name == "protein" or field.name == "carbohydrates" or field.name == "fat" %}
      {% include "tracker/components/form_field.html" with field=field %}
    {% endif %}
  {% endfor %}
</details>
```

For exercises, render common fields, `formset.non_form_errors`, `formset.management_form`, and:

```django
<details data-strength-section{% if strength_open %} open{% endif %}>
  <summary>力量训练明细</summary>
  <div data-strength-formset="{{ formset.prefix }}" data-max-forms="20">
    <div data-formset-rows>
      {% for strength_form in formset.forms %}
        {% include "tracker/components/strength_row.html" with strength_form=strength_form row_number=forloop.counter %}
      {% endfor %}
    </div>
    <template data-formset-template>
      {% include "tracker/components/strength_row.html" with strength_form=formset.empty_form row_number="__number__" %}
    </template>
    <button type="button" class="secondary-button" data-add-row>添加动作</button>
    <p data-formset-limit hidden>最多添加 20 条。</p>
  </div>
</details>
```

Measurement forms render all visible fields using the field partial. Wrap the submit button in `<div class="form-actions"><button type="submit">保存</button></div>`.

Add `{% block scripts %}` to `base.html` before `draft-form.js`, and in `record_form.html` load `record-form.js` through that block. This preserves no-JavaScript server rendering while allowing record-specific enhancement.

- [ ] **Step 8: Run focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/tracker/test_crud.py tests/tracker/test_isolation.py tests/browser/test_mobile_flows.py::test_record_form_enables_non_sensitive_draft_recovery -q`

Expected: typed context, sections, field errors, input modes, and all existing CRUD/isolation tests pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add tracker/forms.py tracker/views/records.py templates/base.html templates/tracker/record_form.html templates/tracker/components tests/tracker/test_crud.py tests/browser/test_mobile_flows.py
git commit -m "feat: structure mobile record forms"
```

### Task 2: Add dynamic strength rows with server-compatible deletion

**Files:**
- Create: `static/js/record-form.js`
- Modify: `static/css/app.css`
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Write a failing browser test for add, focus, delete, and save**

At 360 pixels, authenticate and open `/exercises/new/`. Select `strength`, assert the details opens, click “添加动作” twice, and verify there are three visible rows and focus is in `strength_sets-2-exercise_name`. Fill all three, remove the middle row, submit, and assert the saved exercise has only the first and third names in order.

Also assert each add/remove button has a bounding-box height of at least 44 pixels and the document does not overflow horizontally.

- [ ] **Step 2: Write a failing browser test for the 20-row limit**

Add rows until 20 visible rows exist. Assert the add button is disabled, “最多添加 20 条。” is visible, and a further click cannot create row 21.

- [ ] **Step 3: Run browser tests and verify RED**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q -k "strength_rows or strength_limit"`

Expected: strength details does not react and add/remove controls have no behavior.

- [ ] **Step 4: Implement `record-form.js`**

Create an IIFE that finds `[data-strength-formset]` and implements:

```javascript
const total = container.querySelector('[name$="-TOTAL_FORMS"]');
const rows = container.querySelector("[data-formset-rows]");
const template = container.querySelector("[data-formset-template]");
const addButton = container.querySelector("[data-add-row]");
const max = Number(container.dataset.maxForms || 20);

const activeRows = () => [...rows.querySelectorAll("[data-formset-row]")]
  .filter((row) => !row.hidden && !row.querySelector('[name$="-DELETE"]')?.checked);

const sync = () => {
  activeRows().forEach((row, index) => {
    row.querySelector("[data-row-number]").textContent = String(index + 1);
    const order = row.querySelector('[name$="-order"]');
    if (order) order.value = String(index);
  });
  const atLimit = activeRows().length >= max;
  addButton.disabled = atLimit;
  container.querySelector("[data-formset-limit]").hidden = !atLimit;
};
```

`addRow({focus = true} = {})` replaces every `__prefix__` and `__number__`, appends the row, increments `TOTAL_FORMS`, calls `sync`, dispatches a bubbling `input` event on the form, and focuses the new action-name input when requested.

Delegated remove clicks set the row's DELETE checkbox, hide the row, and if no active row remains call `addRow({focus: false})`. They then call `sync` and dispatch `input`.

Expose only:

```javascript
window.healthRecordForms = {
  ensureTotal(prefix, requestedTotal) {
    const target = document.querySelector(`[data-strength-formset="${CSS.escape(prefix)}"]`);
    while (Number(target.querySelector('[name$="-TOTAL_FORMS"]').value) < requestedTotal) {
      addRowFor(target, {focus: false});
    }
  },
  syncAll,
};
```

Listen for exercise-type changes: selecting `strength` opens `[data-strength-section]`; switching away closes it without clearing values. Listen for `health:draft-restored` to open nutrition when any nutrition input has a value, open strength when content exists, apply restored DELETE states, and call `syncAll`.

- [ ] **Step 5: Add progressive styles**

Style `details`, `.strength-row`, `.secondary-button`, and `.form-actions`. Ensure secondary buttons are 44 pixels high, fieldsets fit within the page, hidden rows remain hidden, and controls inherit existing font sizing.

- [ ] **Step 6: Run browser tests and verify GREEN**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q -k "strength_rows or strength_limit"`

Expected: add, focus, delete, save, limit, touch-target, and overflow assertions pass.

- [ ] **Step 7: Run server-side formset regressions**

Run: `.venv/bin/pytest tests/tracker/test_crud.py tests/tracker/test_isolation.py -q`

Expected: multi-row POST, 20-row enforcement, child-ID tampering, transaction rollback, and owner isolation remain green.

- [ ] **Step 8: Commit Task 2**

```bash
git add static/js/record-form.js static/css/app.css tests/browser/test_mobile_flows.py
git commit -m "feat: manage strength rows on mobile"
```

### Task 3: Preserve dynamic rows in local drafts

**Files:**
- Modify: `static/js/draft-form.js`
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Write a failing three-row draft recovery test**

Open a new exercise, add to three total rows, fill distinct action names, wait for draft persistence, reload, and assert all three rows and values return. Assert the stored JSON contains `__formset_totals.strength_sets == 3` and contains no key ending in `-id`.

- [ ] **Step 2: Write a failing server-prefill precedence test**

Store a legacy draft for `/exercises/new/` with `__formset_totals.strength_sets == 1`. Open a copy URL whose server source has three strength rows. Assert all three server rows remain rendered and none are removed by draft restoration.

Add a nutrition draft test that restores calories on `/meals/new/` and asserts the nutrition details automatically opens.

- [ ] **Step 3: Run draft browser tests and verify RED**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q -k "dynamic_draft or prefill_precedence or nutrition_draft"`

Expected: dynamic rows are missing after reload and restored nutrition remains collapsed.

- [ ] **Step 4: Refactor draft field discovery and storage**

Replace the one-time `safeFields` array with a function:

```javascript
const safeFields = () => [...form.elements].filter((field) =>
  field.name && field.name !== "csrfmiddlewaretoken" &&
  !/-(TOTAL_FORMS|INITIAL_FORMS|MIN_NUM_FORMS|MAX_NUM_FORMS)$/.test(field.name) &&
  !/-\d+-id$/.test(field.name) &&
  !["password", "file", "submit"].includes(field.type)
);
```

Before restoring values, read `draft.__formset_totals` and call `window.healthRecordForms?.ensureTotal(prefix, count)` for each positive integer count. This call may add rows but must never reduce the existing server total.

After creating rows, call `safeFields()` and restore values. Then dispatch:

```javascript
document.dispatchEvent(new CustomEvent("health:draft-restored", {detail: {form}}));
```

- [ ] **Step 5: Save formset totals and tolerate storage failure**

In `saveDraft`, call `safeFields()` each time, add:

```javascript
draft.__formset_totals = {};
form.querySelectorAll("[data-strength-formset]").forEach((container) => {
  const prefix = container.dataset.strengthFormset;
  const total = container.querySelector('[name$="-TOTAL_FORMS"]');
  draft.__formset_totals[prefix] = Number(total.value);
});
```

Wrap `localStorage.setItem` in `try/catch` so a quota or privacy-mode failure does not prevent submit-token creation or normal form submission.

- [ ] **Step 6: Run draft browser tests and verify GREEN**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q -k "dynamic_draft or prefill_precedence or nutrition_draft"`

Expected: dynamic rows, copy precedence, nutrition expansion, and ID exclusion pass.

- [ ] **Step 7: Run all existing draft and copy flows**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q`

Expected: legacy draft recovery, failed-submit persistence, successful-submit cleanup, recent-record copy, and all new draft tests pass.

- [ ] **Step 8: Commit Task 3**

```bash
git add static/js/draft-form.js tests/browser/test_mobile_flows.py
git commit -m "feat: restore dynamic record drafts"
```

### Task 4: Complete responsive acceptance and review

**Files:**
- Modify: `static/css/app.css`
- Modify: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Add sticky-action and multi-width acceptance assertions**

For meal, exercise, and measurement forms at widths 360, 390, 430, and 1280, assert no document overflow. At mobile widths assert `.form-actions` uses `position: sticky`, the save button is at least 44 pixels high, and the bottom padding keeps the action area above `.bottom-nav`. At 1280 pixels assert the form remains inside the 720-pixel page width.

- [ ] **Step 2: Run responsive tests and verify RED or identify existing coverage**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest tests/browser/test_mobile_flows.py -q -k "sticky or supported_widths"`

Expected: new sticky-action assertions fail until final CSS is present; existing overflow assertions remain green.

- [ ] **Step 3: Finish responsive styles**

Use:

```css
.form-actions { position: sticky; bottom: calc(68px + env(safe-area-inset-bottom)); z-index: 5; margin: 20px -8px -8px; padding: 8px; background: var(--surface); border-top: 1px solid var(--line); }
@media (min-width: 720px) { .form-actions { position: static; margin: 20px 0 0; padding: 0; border-top: 0; } }
```

Adjust only if browser measurements show overlap; keep the 44-pixel global button minimum.

- [ ] **Step 4: Run full verification**

Run: `DJANGO_ALLOW_ASYNC_UNSAFE=true .venv/bin/pytest -q`

Then run: `.venv/bin/python manage.py check && git diff --check`

Expected: no failures, no Django check issues, and no whitespace errors.

- [ ] **Step 5: Request independent review and resolve findings**

Review formset management counts, child IDs, delete semantics, 20-row final count, edit behavior, no-JavaScript fallback, draft schema migration, copy-versus-draft precedence, storage failures, field-error rendering, keyboard attributes, and mobile overlap. Resolve every Critical and Important finding.

- [ ] **Step 6: Commit and push**

```bash
git add tracker/forms.py tracker/views/records.py templates static/js static/css/app.css tests docs/superpowers/plans/2026-09-24-mobile-record-form.md
git commit -m "feat: improve mobile record forms"
git push origin feature/health-app
```
