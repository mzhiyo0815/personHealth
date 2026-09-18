import csv
import io
import json

import pytest
from django.contrib.auth import get_user_model

from tracker.models import Exercise, Meal, Measurement, StrengthSet, UserGoal


@pytest.mark.django_db
def test_export_contains_only_current_users_records(client, user, other_user):
    own = Meal.objects.create(user=user, meal_type="lunch", food="own")
    Meal.objects.create(user=other_user, meal_type="dinner", food="secret")
    own_exercise = Exercise.objects.create(user=user, exercise_type="strength", duration_minutes=30, intensity="moderate")
    other_exercise = Exercise.objects.create(user=other_user, exercise_type="strength", duration_minutes=60, intensity="hard")
    own_set = StrengthSet.objects.create(exercise=own_exercise, exercise_name="深蹲", sets=3, reps_per_set=8)
    StrengthSet.objects.create(exercise=other_exercise, exercise_name="秘密动作", sets=5, reps_per_set=5)
    own_measurement = Measurement.objects.create(user=user, kind="weight", value=70)
    Measurement.objects.create(user=other_user, kind="weight", value=99)
    UserGoal.objects.create(user=user, target_weight=65)
    UserGoal.objects.create(user=other_user, target_weight=88)
    client.force_login(user)

    response = client.get("/me/export.json")
    content = b"".join(response.streaming_content)
    body = json.loads(content)

    assert response.status_code == 200
    assert [row["id"] for row in body["meals"]] == [str(own.id)]
    assert [row["id"] for row in body["exercises"]] == [str(own_exercise.id)]
    assert [row["id"] for row in body["exercises"][0]["strength_sets"]] == [str(own_set.id)]
    assert [row["id"] for row in body["measurements"]] == [str(own_measurement.id)]
    assert body["goal"]["target_weight"] == "65.00"
    assert set(body) == {"phone", "goal", "meals", "exercises", "measurements"}
    assert "secret" not in content.decode()
    assert "password" not in content.decode().lower()
    assert response.streaming is True


@pytest.mark.django_db
def test_profile_updates_current_users_goals(client, user):
    client.force_login(user)

    response = client.post(
        "/me/",
        {
            "target_weight": "65.5",
            "weekly_exercise_minutes": 180,
            "weekly_strength_sessions": 3,
            "show_calories": "on",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert str(user.goal.target_weight) == "65.50"
    assert user.goal.weekly_exercise_minutes == 180


@pytest.mark.django_db
def test_password_change_preserves_authenticated_session(client, user):
    client.force_login(user)

    response = client.post(
        "/me/password/",
        {
            "old_password": "safe-pass-123",
            "new_password1": "new-safe-pass-456",
            "new_password2": "new-safe-pass-456",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("new-safe-pass-456")
    assert client.session["_auth_user_id"] == str(user.pk)
    assert client.get("/me/").status_code == 200


@pytest.mark.django_db
def test_csv_export_is_utf8_and_contains_only_current_user(client, user, other_user):
    Meal.objects.create(user=user, meal_type="breakfast", food="豆浆")
    Meal.objects.create(user=other_user, meal_type="breakfast", food="秘密")
    own_exercise = Exercise.objects.create(user=user, exercise_type="strength", duration_minutes=30, intensity="moderate")
    other_exercise = Exercise.objects.create(user=other_user, exercise_type="strength", duration_minutes=60, intensity="hard")
    own_set = StrengthSet.objects.create(exercise=own_exercise, exercise_name="深蹲", sets=3, reps_per_set=8)
    StrengthSet.objects.create(exercise=other_exercise, exercise_name="秘密动作", sets=5, reps_per_set=5)
    own_measurement = Measurement.objects.create(user=user, kind="waist", value=80)
    Measurement.objects.create(user=other_user, kind="waist", value=120)
    UserGoal.objects.create(user=user, target_weight=65)
    UserGoal.objects.create(user=other_user, target_weight=88)
    client.force_login(user)

    response = client.get("/me/export.csv")
    content = b"".join(response.streaming_content)
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert any(row["food"] == "豆浆" for row in rows)
    assert all(row.get("food") != "秘密" for row in rows)
    assert {row["id"] for row in rows if row["record_type"] == "exercise"} == {str(own_exercise.id)}
    assert {row["id"] for row in rows if row["record_type"] == "strength_set"} == {str(own_set.id)}
    assert {row["id"] for row in rows if row["record_type"] == "measurement"} == {str(own_measurement.id)}
    assert [row["target_weight"] for row in rows if row["record_type"] == "goal"] == ["65.00"]
    assert response.streaming is True


@pytest.mark.django_db
def test_profile_get_does_not_create_goal(client, user):
    client.force_login(user)
    assert client.get("/me/").status_code == 200
    assert not hasattr(user, "goal")


@pytest.mark.django_db
def test_csv_export_escapes_formula_prefixes(client, user):
    Meal.objects.create(user=user, meal_type="lunch", food="=HYPERLINK(\"bad\")")
    client.force_login(user)
    response = client.get("/me/export.csv")
    content = b"".join(response.streaming_content).decode("utf-8-sig")
    assert "'=HYPERLINK" in content
