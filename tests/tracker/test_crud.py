import pytest
from django.db import connection

from tracker.forms import (
    BaseStrengthSetFormSet,
    ExerciseForm,
    MealForm,
    MeasurementForm,
)
from tracker.models import Exercise, Meal, Measurement, StrengthSet


@pytest.mark.django_db
def test_owner_can_edit_own_meal(client, user):
    meal = Meal.objects.create(
        user=user,
        meal_type="breakfast",
        food="鸡蛋",
        portion="2 个",
        fullness=7,
    )
    client.force_login(user)

    response = client.post(
        f"/meals/{meal.pk}/edit/",
        {
            "occurred_at": meal.occurred_at.strftime("%Y-%m-%dT%H:%M"),
            "meal_type": "breakfast",
            "food": "鸡蛋和豆浆",
            "portion": "2 个、300 ml",
            "fullness": 8,
        },
    )

    assert response.status_code == 302
    meal.refresh_from_db()
    assert meal.food == "鸡蛋和豆浆"


def test_record_forms_do_not_expose_owner_or_photo_fields():
    forbidden_fields = {"user", "photo_url", "created_at", "updated_at"}
    assert forbidden_fields.isdisjoint(MealForm().fields)
    assert forbidden_fields.isdisjoint(ExerciseForm().fields)
    assert forbidden_fields.isdisjoint(MeasurementForm().fields)


def test_forms_reject_negative_nutrition_and_excessive_duration():
    meal_form = MealForm(
        data={
            "occurred_at": "2026-09-18T08:00",
            "meal_type": "breakfast",
            "food": "鸡蛋",
            "calories": "-1",
        }
    )
    exercise_form = ExerciseForm(
        data={
            "occurred_at": "2026-09-18T18:00",
            "exercise_type": "walking",
            "duration_minutes": 1441,
            "intensity": "easy",
        }
    )

    assert not meal_form.is_valid()
    assert "calories" in meal_form.errors
    assert not exercise_form.is_valid()
    assert "duration_minutes" in exercise_form.errors


@pytest.mark.django_db
def test_meal_create_allows_blank_nutrition_and_assigns_owner(client, user):
    client.force_login(user)

    response = client.post(
        "/meals/new/",
        {
            "occurred_at": "2026-09-18T08:00",
            "meal_type": "breakfast",
            "food": "鸡蛋和豆浆",
            "portion": "2 个、300 ml",
            "fullness": 7,
        },
    )

    assert response.status_code == 302
    meal = user.meals.get()
    assert meal.calories is None
    assert meal.photo_url == ""


@pytest.mark.django_db
def test_successful_create_redirects_to_existing_page(client, user):
    client.force_login(user)

    response = client.post(
        "/meals/new/",
        {
            "occurred_at": "2026-09-18T08:00",
            "meal_type": "breakfast",
            "food": "鸡蛋",
        },
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain == [("/", 302)]


@pytest.mark.django_db
def test_exercise_create_saves_multiple_strength_sets(client, user):
    client.force_login(user)

    response = client.post(
        "/exercises/new/",
        {
            "occurred_at": "2026-09-18T18:00",
            "exercise_type": "strength",
            "duration_minutes": 45,
            "intensity": "moderate",
            "notes": "下肢训练",
            "strength_sets-TOTAL_FORMS": 2,
            "strength_sets-INITIAL_FORMS": 0,
            "strength_sets-MIN_NUM_FORMS": 0,
            "strength_sets-MAX_NUM_FORMS": 20,
            "strength_sets-0-exercise_name": "深蹲",
            "strength_sets-0-sets": 3,
            "strength_sets-0-reps_per_set": 8,
            "strength_sets-0-load_kg": 40,
            "strength_sets-0-order": 0,
            "strength_sets-1-exercise_name": "箭步蹲",
            "strength_sets-1-sets": 3,
            "strength_sets-1-reps_per_set": 10,
            "strength_sets-1-order": 1,
        },
    )

    assert response.status_code == 302
    exercise = user.exercises.get()
    assert list(
        exercise.strength_sets.values_list("exercise_name", flat=True)
    ) == ["深蹲", "箭步蹲"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("kind", "value", "expected_error"),
    (("weight", "500.01", "500"), ("waist", "300.01", "300")),
)
def test_measurement_rejects_values_above_sensible_limit(
    client, user, kind, value, expected_error
):
    client.force_login(user)

    response = client.post(
        "/measurements/new/",
        {"occurred_at": "2026-09-18T07:00", "kind": kind, "value": value},
    )

    assert response.status_code == 200
    assert expected_error in response.content.decode()
    assert not Measurement.objects.exists()


@pytest.mark.django_db
def test_meal_delete_requires_post(client, user):
    meal = Meal.objects.create(user=user, meal_type="snack", food="苹果")
    client.force_login(user)

    assert client.get(f"/meals/{meal.pk}/delete/").status_code == 405
    assert client.post(f"/meals/{meal.pk}/delete/").status_code == 302
    assert not Meal.objects.filter(pk=meal.pk).exists()


@pytest.mark.django_db
def test_owner_can_create_and_edit_measurement(client, user):
    client.force_login(user)
    create_response = client.post(
        "/measurements/new/",
        {"occurred_at": "2026-09-18T07:00", "kind": "weight", "value": "70.5"},
    )
    measurement = user.measurements.get()

    edit_response = client.post(
        f"/measurements/{measurement.pk}/edit/",
        {"occurred_at": "2026-09-18T07:00", "kind": "weight", "value": "70.2"},
    )

    assert create_response.status_code == 302
    assert edit_response.status_code == 302
    measurement.refresh_from_db()
    assert str(measurement.value) == "70.20"


@pytest.mark.django_db
def test_owner_can_edit_and_delete_exercise(client, user):
    exercise = Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=30,
        intensity="easy",
    )
    client.force_login(user)
    edit_response = client.post(
        f"/exercises/{exercise.pk}/edit/",
        {
            "occurred_at": exercise.occurred_at.strftime("%Y-%m-%dT%H:%M"),
            "exercise_type": "running",
            "duration_minutes": 20,
            "intensity": "hard",
            "strength_sets-TOTAL_FORMS": 0,
            "strength_sets-INITIAL_FORMS": 0,
            "strength_sets-MIN_NUM_FORMS": 0,
            "strength_sets-MAX_NUM_FORMS": 20,
        },
    )

    assert edit_response.status_code == 302
    exercise.refresh_from_db()
    assert exercise.exercise_type == "running"
    assert client.post(f"/exercises/{exercise.pk}/delete/").status_code == 302
    assert not Exercise.objects.filter(pk=exercise.pk).exists()


@pytest.mark.django_db
def test_exercise_create_rolls_back_when_strength_save_fails(
    client, user, monkeypatch
):
    client.force_login(user)

    def fail_save(*args, **kwargs):
        raise RuntimeError("simulated formset failure")

    monkeypatch.setattr(BaseStrengthSetFormSet, "save", fail_save)

    with pytest.raises(RuntimeError, match="simulated formset failure"):
        client.post(
            "/exercises/new/",
            {
                "occurred_at": "2026-09-18T18:00",
                "exercise_type": "strength",
                "duration_minutes": 45,
                "intensity": "moderate",
                "strength_sets-TOTAL_FORMS": 1,
                "strength_sets-INITIAL_FORMS": 0,
                "strength_sets-MIN_NUM_FORMS": 0,
                "strength_sets-MAX_NUM_FORMS": 20,
                "strength_sets-0-exercise_name": "深蹲",
                "strength_sets-0-sets": 3,
                "strength_sets-0-reps_per_set": 8,
                "strength_sets-0-order": 0,
            },
        )

    assert not Exercise.objects.exists()
    assert not StrengthSet.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_exercise_edit_validates_strength_sets_inside_transaction(
    client, user, monkeypatch
):
    exercise = Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=30,
        intensity="moderate",
    )
    client.force_login(user)
    original_is_valid = BaseStrengthSetFormSet.is_valid
    observed_atomic_state = []

    def observe_transaction(formset):
        observed_atomic_state.append(connection.in_atomic_block)
        return original_is_valid(formset)

    monkeypatch.setattr(BaseStrengthSetFormSet, "is_valid", observe_transaction)

    response = client.post(
        f"/exercises/{exercise.pk}/edit/",
        {
            "occurred_at": exercise.occurred_at.strftime("%Y-%m-%dT%H:%M"),
            "exercise_type": "strength",
            "duration_minutes": 30,
            "intensity": "moderate",
            "strength_sets-TOTAL_FORMS": 0,
            "strength_sets-INITIAL_FORMS": 0,
            "strength_sets-MIN_NUM_FORMS": 0,
            "strength_sets-MAX_NUM_FORMS": 20,
        },
    )

    assert response.status_code == 302
    assert observed_atomic_state
    assert all(observed_atomic_state)
