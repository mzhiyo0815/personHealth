# Health Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first cloud-backed web app for recording meals, exercise, weight, and waist measurements with phone-number/password login and 7/30-day trends.

**Architecture:** Use Django 5.2 LTS as a server-rendered monolith with PostgreSQL in production and SQLite for isolated tests. Split authentication into `accounts`, health records into `tracker`, and keep calculations in pure service functions so they can be unit-tested independently of views.

**Tech Stack:** Python 3.13, Django 5.2 LTS, PostgreSQL, Gunicorn, WhiteNoise, django-environ, django-ratelimit, pytest-django, pytest-playwright, HTML/CSS, vanilla JavaScript, inline SVG charts.

---

## File map

- `manage.py` — Django command entry point.
- `config/settings.py` — environment, database, security, static files, auth configuration.
- `config/urls.py` — top-level URL routing.
- `accounts/models.py` — phone-number user model and manager.
- `accounts/forms.py` — registration, login, and password-change validation.
- `accounts/views.py` — registration/login/logout/password flows and throttling.
- `tracker/models.py` — goals, meals, exercises, strength sets, and measurements.
- `tracker/forms.py` — typed record forms and strength formset.
- `tracker/services/trends.py` — 7/30-day aggregation.
- `tracker/services/export.py` — current-user JSON/CSV export.
- `tracker/views/*.py` — today, history, CRUD, trends, profile/export endpoints.
- `templates/` — base, auth, dashboard, forms, history, trends, and profile pages.
- `static/css/app.css` — mobile-first visual system.
- `static/js/draft-form.js` — local unsaved-form recovery.
- `tests/` — model, auth, isolation, CRUD, trend, export, and responsive smoke tests.
- `requirements.txt`, `pytest.ini`, `.env.example`, `Procfile` — reproducible runtime, test, and deployment configuration.

### Task 1: Bootstrap a tested Django project

**Files:**
- Create: `requirements.txt`, `pytest.ini`
- Create: `.env.example`
- Create: `manage.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`
- Create: `accounts/`, `tracker/`, `templates/`, `static/css/`, `static/js/`, `tests/test_smoke.py`

- [ ] **Step 1: Add pinned dependency ranges**

```text
Django>=5.2,<5.3
psycopg[binary]>=3.2,<4
gunicorn>=23,<24
whitenoise>=6.9,<7
django-environ>=0.12,<1
django-ratelimit>=4.1,<5
pytest>=8.3,<9
pytest-django>=4.11,<5
pytest-playwright>=0.7,<1
```

Create `pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
```

- [ ] **Step 2: Create the environment template**

```dotenv
DEBUG=true
SECRET_KEY=change-me
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
```

- [ ] **Step 3: Write the failing smoke test**

```python
def test_health_endpoint(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Run the test and confirm failure**

Run: `pytest tests/test_smoke.py -q`
Expected: FAIL because the Django project or `/health/` route does not exist.

- [ ] **Step 5: Scaffold the project and implement the health route**

Run: `django-admin startproject config . && python manage.py startapp accounts && python manage.py startapp tracker`

Add to `config/urls.py`:

```python
from django.http import JsonResponse
from django.urls import include, path

urlpatterns = [
    path("health/", lambda request: JsonResponse({"status": "ok"})),
    path("accounts/", include("accounts.urls")),
    path("", include("tracker.urls")),
]
```

- [ ] **Step 6: Run the test and commit**

Run: `pytest tests/test_smoke.py -q`
Expected: `1 passed`.

```bash
git add requirements.txt pytest.ini .env.example manage.py config accounts tracker tests
git commit -m "chore: bootstrap health tracker"
```

### Task 2: Implement phone-number authentication

**Files:**
- Create: `accounts/models.py`, `accounts/forms.py`, `accounts/views.py`, `accounts/urls.py`
- Create: `templates/accounts/register.html`, `templates/accounts/login.html`
- Test: `tests/accounts/test_auth.py`
- Modify: `config/settings.py`

- [ ] **Step 1: Write failing registration and isolation tests**

```python
import pytest
from django.contrib.auth import get_user_model

@pytest.mark.django_db
def test_phone_registration_hashes_password(client):
    response = client.post("/accounts/register/", {
        "phone": "13800138000", "password1": "safe-pass-123", "password2": "safe-pass-123"
    })
    assert response.status_code == 302
    user = get_user_model().objects.get(phone="13800138000")
    assert user.check_password("safe-pass-123")
    assert user.password != "safe-pass-123"

@pytest.mark.django_db
def test_password_shorter_than_eight_is_rejected(client):
    response = client.post("/accounts/register/", {
        "phone": "13800138000", "password1": "1234567", "password2": "1234567"
    })
    assert response.status_code == 200
    assert "至少 8 位" in response.content.decode()
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/accounts/test_auth.py -q`
Expected: FAIL because the custom user and routes do not exist.

- [ ] **Step 3: Implement the custom user before the first migration**

```python
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra):
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        return self.create_user(phone, password, is_staff=True, is_superuser=True, **extra)

class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    objects = UserManager()
    USERNAME_FIELD = "phone"
```

Set `AUTH_USER_MODEL = "accounts.User"`, install `accounts` and `tracker`, and use Django password validators including `MinimumLengthValidator` with `min_length: 8`.

- [ ] **Step 4: Implement forms and views**

Use `UserCreationForm` with `phone` as the identifying field, `AuthenticationForm` with label “手机号”, Django `login()`/`logout()`, generic failure text, and `@ratelimit(key="ip", rate="5/m", block=True)` on login and registration POST handlers.

- [ ] **Step 5: Create migrations and run auth tests**

Run: `python manage.py makemigrations accounts && python manage.py migrate && pytest tests/accounts/test_auth.py -q`
Expected: all auth tests PASS.

- [ ] **Step 6: Commit**

```bash
git add accounts config templates/accounts tests/accounts
git commit -m "feat: add phone password authentication"
```

### Task 3: Add health-record domain models

**Files:**
- Create: `tracker/models.py`
- Test: `tests/tracker/test_models.py`

- [ ] **Step 1: Write failing model validation tests**

```python
import pytest
from django.core.exceptions import ValidationError
from tracker.models import Meal, Measurement

@pytest.mark.django_db
def test_meal_allows_blank_nutrition(user):
    meal = Meal(user=user, meal_type="breakfast", food="鸡蛋和豆浆", portion="2个、300ml", fullness=7)
    meal.full_clean()

@pytest.mark.django_db
def test_measurement_rejects_non_positive_value(user):
    item = Measurement(user=user, kind="weight", value=0)
    with pytest.raises(ValidationError):
        item.full_clean()
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/tracker/test_models.py -q`
Expected: FAIL because models are missing.

- [ ] **Step 3: Implement focused models**

Create `UserGoal`, `Meal`, `Exercise`, `StrengthSet`, and `Measurement`. All records use UUID primary keys, `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)`, `occurred_at`, `created_at`, and `updated_at`. Nutrition and load fields are nullable `DecimalField`s. Add `photo_url = models.URLField(blank=True)` but never expose it in a form. Use `CheckConstraint` for positive duration/value and choices for meal type, intensity, exercise type, and measurement kind.

- [ ] **Step 4: Add indexes and uniqueness rules**

Index `(user, occurred_at)` on record tables. Make `UserGoal.user` one-to-one. Add `(exercise, order)` ordering for strength sets. Do not make measurements unique per day; trend services select the latest item for each day.

- [ ] **Step 5: Migrate and verify tests**

Run: `python manage.py makemigrations tracker && python manage.py migrate && pytest tests/tracker/test_models.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tracker/models.py tracker/migrations tests/tracker/test_models.py
git commit -m "feat: add health record models"
```

### Task 4: Build typed forms and CRUD authorization

**Files:**
- Create: `tracker/forms.py`, `tracker/views/records.py`, `tracker/urls.py`
- Test: `tests/tracker/test_crud.py`, `tests/tracker/test_isolation.py`

- [ ] **Step 1: Write failing cross-account access test**

```python
@pytest.mark.django_db
def test_user_cannot_edit_another_users_meal(client, user, other_user, meal_factory):
    client.force_login(user)
    meal = meal_factory(user=other_user)
    response = client.post(f"/meals/{meal.pk}/edit/", {"food": "changed"})
    assert response.status_code == 404
    meal.refresh_from_db()
    assert meal.food != "changed"
```

- [ ] **Step 2: Run test and confirm failure**

Run: `pytest tests/tracker/test_isolation.py -q`
Expected: FAIL because CRUD views do not exist.

- [ ] **Step 3: Implement forms**

Create `MealForm`, `ExerciseForm`, `StrengthSetFormSet`, and `MeasurementForm`. Exclude `user`, timestamps, and `photo_url`. Validate fullness from 1–10, non-negative nutrition, positive duration, and sensible upper bounds (weight ≤ 500 kg, waist ≤ 300 cm, duration ≤ 1,440 minutes).

- [ ] **Step 4: Implement owner-scoped CRUD views**

Every query must begin with `request.user.meals`, `request.user.exercises`, or `request.user.measurements`; assign `form.instance.user = request.user` server-side. Use POST-only deletion with confirmation pages and transactions when saving an exercise with strength sets.

- [ ] **Step 5: Run CRUD and isolation tests**

Run: `pytest tests/tracker/test_crud.py tests/tracker/test_isolation.py -q`
Expected: PASS, including create/edit/delete and cross-account 404 cases.

- [ ] **Step 6: Commit**

```bash
git add tracker/forms.py tracker/views tracker/urls.py tests/tracker
git commit -m "feat: add owner scoped record CRUD"
```

### Task 5: Implement Today and History pages

**Files:**
- Create: `tracker/views/dashboard.py`, `tracker/views/history.py`
- Create: `templates/base.html`, `templates/tracker/today.html`, `templates/tracker/history.html`, `templates/tracker/record_form.html`, `templates/tracker/confirm_delete.html`
- Test: `tests/tracker/test_dashboard.py`

- [ ] **Step 1: Write the failing completion-state test**

```python
@pytest.mark.django_db
def test_today_marks_recorded_meal_and_exercise(client, user, meal_factory, exercise_factory):
    client.force_login(user)
    meal_factory(user=user, meal_type="breakfast")
    exercise_factory(user=user)
    response = client.get("/")
    assert response.context["completion"]["breakfast"] is True
    assert response.context["completion"]["exercise"] is True
```

- [ ] **Step 2: Implement dashboard aggregation**

Use the user’s configured timezone, filter `occurred_at` to the local day, and return completion flags for breakfast, lunch, dinner, snack, exercise, weight, and waist.

- [ ] **Step 3: Implement date-grouped history**

Paginate by day, default newest first, and allow a date query parameter. Render edit/delete links only for the owner-scoped objects already loaded by the view.

- [ ] **Step 4: Run tests and accessibility checks**

Run: `pytest tests/tracker/test_dashboard.py -q`
Expected: PASS. Verify form labels, input modes (`decimal`, `numeric`, `tel`), focus styles, and no horizontal overflow at 360 px.

- [ ] **Step 5: Commit**

```bash
git add tracker/views templates tests/tracker/test_dashboard.py
git commit -m "feat: add today and history experiences"
```

### Task 6: Add trend calculations and SVG charts

**Files:**
- Create: `tracker/services/trends.py`, `tracker/views/trends.py`, `templates/tracker/trends.html`, `templates/components/line_chart.svg.html`
- Test: `tests/tracker/test_trends.py`

- [ ] **Step 1: Write failing aggregation tests**

```python
def test_latest_measurement_per_day_wins():
    rows = [("2026-09-16", 88.0), ("2026-09-16", 87.8), ("2026-09-17", 87.6)]
    assert latest_daily_values(rows) == [("2026-09-16", 87.8), ("2026-09-17", 87.6)]

def test_missing_nutrition_does_not_become_zero():
    assert average_optional([None, None]) is None
```

- [ ] **Step 2: Implement pure calculation functions**

Implement `latest_daily_values`, `measurement_series`, `weekly_exercise_summary`, `meal_completion_series`, and `optional_nutrition_average`. Return plain dataclasses/dicts; keep ORM queries in the view.

- [ ] **Step 3: Implement accessible SVG charts**

Render server-side inline SVG with `<title>` and a tabular fallback. Support `?range=7` and `?range=30`; do not draw a trend line when fewer than two points exist.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/tracker/test_trends.py -q`
Expected: PASS.

```bash
git add tracker/services/trends.py tracker/views/trends.py templates tests/tracker/test_trends.py
git commit -m "feat: add health trends"
```

### Task 7: Add profile, password change, and export

**Files:**
- Create: `tracker/views/profile.py`, `tracker/services/export.py`, `templates/tracker/profile.html`
- Test: `tests/tracker/test_export.py`

- [ ] **Step 1: Write failing export isolation test**

```python
@pytest.mark.django_db
def test_export_contains_only_current_users_records(client, user, other_user, meal_factory):
    client.force_login(user)
    own = meal_factory(user=user, food="own")
    meal_factory(user=other_user, food="secret")
    response = client.get("/me/export.json")
    body = response.json()
    assert [row["id"] for row in body["meals"]] == [str(own.id)]
    assert "secret" not in response.content.decode()
```

- [ ] **Step 2: Implement profile and export**

Use Django’s `PasswordChangeView`, preserve the authenticated session, upsert `UserGoal`, and stream UTF-8 JSON plus CSV files generated only from `request.user` querysets. Never export password or session data.

- [ ] **Step 3: Run tests and commit**

Run: `pytest tests/tracker/test_export.py -q`
Expected: PASS.

```bash
git add tracker/views/profile.py tracker/services/export.py templates/tracker/profile.html tests/tracker/test_export.py
git commit -m "feat: add goals password change and export"
```

### Task 8: Add mobile styling and resilient draft recovery

**Files:**
- Create: `static/css/app.css`, `static/js/draft-form.js`
- Modify: `templates/base.html`, all record-form templates
- Test: `tests/browser/test_mobile_flows.py`

- [ ] **Step 1: Write the failing browser flow**

```python
def test_unsaved_meal_draft_survives_reload(page, live_server, logged_in_user):
    page.goto(f"{live_server.url}/meals/new/")
    page.fill("#id_food", "鸡蛋和无糖豆浆")
    page.reload()
    assert page.input_value("#id_food") == "鸡蛋和无糖豆浆"
```

- [ ] **Step 2: Implement the mobile design tokens**

Use a 360 px minimum viewport, 16 px body type, 44 px minimum tap targets, fixed bottom navigation, safe-area padding, clear validation states, and the approved green quick-entry dashboard. Add `aria-current` to navigation and visible keyboard focus.

- [ ] **Step 3: Implement draft recovery**

Store only non-sensitive form values in `localStorage` under a key containing user ID and form type; debounce writes, restore on reload, and clear after a successful save. Never store passwords or authentication tokens.

- [ ] **Step 4: Run browser and unit tests**

Run: `pytest tests/browser/test_mobile_flows.py -q && pytest -q`
Expected: all tests PASS and pages show no horizontal scroll at 360, 390, and 430 px.

- [ ] **Step 5: Commit**

```bash
git add static templates tests/browser
git commit -m "feat: polish mobile recording flows"
```

### Task 9: Harden production configuration and deploy

**Files:**
- Modify: `config/settings.py`
- Create: `Procfile`, `docs/operations.md`
- Test: `tests/test_security_settings.py`

- [ ] **Step 1: Write failing production-setting tests**

```python
def test_production_requires_https(settings):
    assert settings.SECURE_SSL_REDIRECT is True
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
```

- [ ] **Step 2: Implement environment-aware production settings**

Load secrets from environment variables; enable HTTPS redirect, secure cookies, HSTS after HTTPS is verified, trusted origins, WhiteNoise static files, database connection health checks, and structured logs that exclude request bodies on auth routes.

- [ ] **Step 3: Add deployment runbook**

Document provisioning PostgreSQL, setting environment variables, running `python manage.py migrate`, `python manage.py collectstatic --noinput`, creating an admin account, rotating secrets, database backups, and administrator password-reset procedure.

- [ ] **Step 4: Run full verification**

Run: `python manage.py check --deploy && pytest -q`
Expected: no actionable deployment warnings and all tests PASS.

- [ ] **Step 5: Perform acceptance walkthrough**

Verify two real test accounts cannot access each other’s records; create/edit/delete each record type; leave nutrition blank; add multiple strength sets; inspect 7/30-day charts; reload an unsaved form; export data; and confirm there are no image-upload requests or storage dependencies.

- [ ] **Step 6: Commit**

```bash
git add config Procfile docs/operations.md tests/test_security_settings.py
git commit -m "chore: harden and document deployment"
```

## Final release gate

- [ ] Run `pytest -q` and record the passing test count.
- [ ] Run `python manage.py check --deploy` against production-like environment variables.
- [ ] Verify migrations apply to an empty PostgreSQL database.
- [ ] Verify the four main flows at 360 px and desktop widths.
- [ ] Confirm password values, tokens, and full request bodies are absent from logs.
- [ ] Confirm the production build contains no photo upload endpoint, storage credential, or photo input.
- [ ] Confirm the data export opens as UTF-8 and contains only the signed-in user’s records.
