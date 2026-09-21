import pytest
from django.utils import timezone

from tracker.models import Exercise, Meal, Measurement, StrengthSet


@pytest.mark.django_db
def test_record_form_enables_non_sensitive_draft_recovery(client, user):
    client.force_login(user)
    response = client.get("/meals/new/")
    content = response.content.decode()

    assert 'data-user-id="' in content
    assert 'data-draft-form="record"' in content
    assert 'src="/static/js/draft-form.js"' in content


@pytest.mark.django_db
def test_mobile_pages_include_stylesheet_and_accessible_navigation(client, user):
    client.force_login(user)
    content = client.get("/").content.decode()

    assert 'href="/static/css/app.css"' in content
    assert 'class="bottom-nav"' in content
    assert 'aria-current="page"' in content


def test_auth_pages_share_mobile_styles_and_safe_area_viewport(client):
    content = client.get("/accounts/login/").content.decode()

    assert 'href="/static/css/app.css"' in content
    assert "viewport-fit=cover" in content


@pytest.mark.django_db(transaction=True)
def test_all_forms_use_chinese_labels_and_show_units(
    page, live_server, client, user, settings
):
    page.goto(f"{live_server.url}/accounts/register/")
    registration_labels = " ".join(page.locator("label").all_inner_texts())
    assert all(
        label in registration_labels for label in ("手机号", "密码", "确认密码")
    )

    client.force_login(user)
    page.context.add_cookies(
        [{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url": live_server.url,
        }]
    )
    expected_by_path = {
        "/meals/new/": (
            "记录时间",
            "餐次",
            "食物",
            "份量/备注",
            "饱腹感（1–10）",
            "热量（千卡 kcal）",
            "蛋白质（克 g）",
            "碳水化合物（克 g）",
            "脂肪（克 g）",
        ),
        "/exercises/new/": (
            "运动类型",
            "运动时长（分钟）",
            "强度",
            "动作名称",
            "组数",
            "每组次数",
            "负重（千克 kg）",
            "删除本条",
        ),
        "/measurements/new/?kind=weight": (
            "指标类型",
            "数值（体重 kg，腰围 cm）",
        ),
        "/me/": (
            "目标体重（千克 kg）",
            "每周运动目标（分钟）",
            "每周力量训练目标（次）",
            "显示热量",
        ),
        "/me/password/": ("旧密码", "新密码", "确认新密码"),
    }
    forbidden_labels = (
        "Occurred at",
        "Meal type",
        "Food",
        "Portion",
        "Fullness",
        "Calories",
        "Protein",
        "Carbohydrates",
        "Exercise type",
        "Duration minutes",
        "Exercise name",
        "Reps per set",
        "Load kg",
        "Target weight",
        "Old password",
        "New password confirmation",
    )

    for path, expected_labels in expected_by_path.items():
        page.goto(f"{live_server.url}{path}")
        visible_labels = " ".join(page.locator("label").all_inner_texts())
        assert all(label in visible_labels for label in expected_labels)
        assert all(label not in visible_labels for label in forbidden_labels)


@pytest.mark.django_db(transaction=True)
def test_unsaved_meal_draft_survives_reload(page, live_server, client, user, settings):
    client.force_login(user)
    page.context.add_cookies(
        [{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url": live_server.url,
        }]
    )
    page.set_viewport_size({"width": 360, "height": 780})
    page.goto(f"{live_server.url}/meals/new/")
    page.fill("#id_food", "鸡蛋和无糖豆浆")
    page.wait_for_timeout(350)
    saved_drafts = page.evaluate("Object.values(localStorage)")
    assert any("鸡蛋和无糖豆浆" in draft for draft in saved_drafts)
    page.reload()

    assert page.input_value("#id_food") == "鸡蛋和无糖豆浆"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.django_db(transaction=True)
def test_failed_submit_keeps_latest_draft_across_navigation(
    page, live_server, client, user, settings
):
    client.force_login(user)
    page.context.add_cookies(
        [{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url": live_server.url,
        }]
    )
    page.goto(f"{live_server.url}/meals/new/")
    page.fill("#id_occurred_at", "2026-09-18T08:00")
    page.select_option("#id_meal_type", "breakfast")
    page.fill("#id_food", "刚刚输入的草稿")
    page.locator("#id_fullness").evaluate("field => field.removeAttribute('max')")
    page.fill("#id_fullness", "11")
    page.click('button[type="submit"]')
    page.wait_for_load_state()
    assert page.locator(".errorlist").count() > 0
    page.goto(f"{live_server.url}/")
    page.goto(f"{live_server.url}/meals/new/")

    assert page.input_value("#id_food") == "刚刚输入的草稿"


@pytest.mark.django_db(transaction=True)
def test_successful_submit_clears_saved_draft(page, live_server, client, user, settings):
    client.force_login(user)
    page.context.add_cookies(
        [{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url": live_server.url,
        }]
    )
    page.goto(f"{live_server.url}/meals/new/")
    page.fill("#id_occurred_at", "2026-09-18T08:00")
    page.select_option("#id_meal_type", "breakfast")
    page.fill("#id_food", "保存成功的早餐")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/")
    page.goto(f"{live_server.url}/meals/new/")

    assert page.input_value("#id_food") == ""


@pytest.mark.django_db(transaction=True)
def test_mobile_recent_records_prefill_meal_and_exercise(
    page, live_server, client, user, settings
):
    meal = Meal.objects.create(
        user=user,
        meal_type="lunch",
        food="鸡胸肉糙米饭",
        portion="一份",
    )
    exercise = Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=45,
        intensity="moderate",
        notes="上肢训练",
    )
    StrengthSet.objects.create(
        exercise=exercise,
        exercise_name="卧推",
        sets=4,
        reps_per_set=8,
        load_kg=40,
        order=0,
    )
    StrengthSet.objects.create(
        exercise=exercise,
        exercise_name="划船",
        sets=3,
        reps_per_set=10,
        load_kg=30,
        order=1,
    )
    client.force_login(user)
    page.context.add_cookies(
        [{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url": live_server.url,
        }]
    )
    page.set_viewport_size({"width": 360, "height": 780})

    page.goto(f"{live_server.url}/")
    meal_link = page.locator(f'a[href="/meals/new/?copy={meal.pk}"]')
    assert meal_link.bounding_box()["height"] >= 44
    meal_link.click()
    assert page.input_value("#id_food") == "鸡胸肉糙米饭"
    assert page.input_value("#id_portion") == "一份"

    page.goto(f"{live_server.url}/")
    user_id = page.locator("body").get_attribute("data-user-id")
    page.evaluate(
        "entry => localStorage.setItem(entry.key, entry.value)",
        {
            "key": f"health-draft:{user_id}:/exercises/new/",
            "value": '{"strength_sets-TOTAL_FORMS":"1"}',
        },
    )
    exercise_link = page.locator(f'a[href="/exercises/new/?copy={exercise.pk}"]')
    assert exercise_link.bounding_box()["height"] >= 44
    exercise_link.click()
    assert page.input_value("#id_exercise_type") == "strength"
    assert page.input_value("#id_duration_minutes") == "45"
    assert page.input_value("#id_strength_sets-TOTAL_FORMS") == "2"
    assert page.input_value("#id_strength_sets-0-exercise_name") == "卧推"
    assert page.input_value("#id_strength_sets-1-exercise_name") == "划船"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/")
    copied = user.exercises.exclude(pk=exercise.pk).get()
    assert copied.strength_sets.count() == 2


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width", (360, 390, 430, 1280))
def test_primary_flows_do_not_overflow_at_supported_widths(
    page, live_server, client, user, settings, width
):
    meal = Meal.objects.create(
        user=user,
        meal_type="breakfast",
        food="燕麦、鸡蛋、无糖豆浆和水果" * 8,
        portion="一份完整早餐",
        calories=520,
        protein=28,
        carbohydrates=62,
        fat=18,
        occurred_at=timezone.now(),
    )
    exercise = Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=45,
        intensity="moderate",
        notes="全身力量训练",
        occurred_at=meal.occurred_at,
    )
    StrengthSet.objects.create(
        exercise=exercise,
        exercise_name="保加利亚分腿蹲",
        sets=3,
        reps_per_set=10,
        load_kg=20,
    )
    Measurement.objects.create(
        user=user, kind="weight", value=70.2, occurred_at=meal.occurred_at
    )
    Measurement.objects.create(
        user=user, kind="waist", value=82.5, occurred_at=meal.occurred_at
    )
    client.force_login(user)
    page.context.add_cookies(
        [{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url": live_server.url,
        }]
    )
    page.set_viewport_size({"width": width, "height": 800})

    paths = (
        "/",
        "/history/",
        "/trends/",
        "/me/",
        "/meals/new/",
        "/exercises/new/",
        "/measurements/new/?kind=weight",
    )
    for path in paths:
        expected_url = f"{live_server.url}{path}"
        response = page.goto(expected_url)
        assert response.status == 200
        assert page.url == expected_url
        assert page.evaluate(
            "document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth"
        )
        assert page.locator('input[type="file"], img').count() == 0
