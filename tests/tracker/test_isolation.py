import uuid

import pytest

from tracker.models import Exercise, Meal, Measurement, StrengthSet


@pytest.mark.django_db
def test_user_cannot_edit_another_users_meal(client, user, other_user):
    meal = Meal.objects.create(
        user=other_user,
        meal_type="breakfast",
        food="原记录",
    )
    client.force_login(user)

    response = client.post(
        f"/meals/{meal.pk}/edit/",
        {"meal_type": "breakfast", "food": "已篡改"},
    )

    assert response.status_code == 404
    meal.refresh_from_db()
    assert meal.food == "原记录"


@pytest.mark.django_db
@pytest.mark.parametrize("copy_value", ("", "not-a-uuid", str(uuid.uuid4())))
def test_meal_copy_rejects_invalid_or_missing_record(client, user, copy_value):
    client.force_login(user)

    response = client.get("/meals/new/", {"copy": copy_value})

    assert response.status_code == 404


@pytest.mark.django_db
def test_meal_copy_rejects_another_users_record(client, user, other_user):
    meal = Meal.objects.create(
        user=other_user, meal_type="dinner", food="他人的晚餐"
    )
    client.force_login(user)

    response = client.get("/meals/new/", {"copy": meal.pk})

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("copy_value", ("", "not-a-uuid", str(uuid.uuid4())))
def test_exercise_copy_rejects_invalid_or_missing_record(client, user, copy_value):
    client.force_login(user)

    response = client.get("/exercises/new/", {"copy": copy_value})

    assert response.status_code == 404


@pytest.mark.django_db
def test_exercise_copy_rejects_another_users_record(client, user, other_user):
    exercise = Exercise.objects.create(
        user=other_user,
        exercise_type="walking",
        duration_minutes=30,
        intensity="easy",
    )
    client.force_login(user)

    response = client.get("/exercises/new/", {"copy": exercise.pk})

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("record_type", ("exercise", "measurement"))
def test_user_cannot_edit_another_users_other_records(
    client, user, other_user, record_type
):
    if record_type == "exercise":
        record = Exercise.objects.create(
            user=other_user,
            exercise_type="walking",
            duration_minutes=30,
            intensity="easy",
        )
        url = f"/exercises/{record.pk}/edit/"
    else:
        record = Measurement.objects.create(
            user=other_user, kind="weight", value=70
        )
        url = f"/measurements/{record.pk}/edit/"
    client.force_login(user)

    response = client.post(url, {})

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("record_type", ("meal", "exercise", "measurement"))
def test_user_cannot_delete_another_users_records(
    client, user, other_user, record_type
):
    if record_type == "meal":
        record = Meal.objects.create(
            user=other_user, meal_type="lunch", food="他人的午餐"
        )
        url = f"/meals/{record.pk}/delete/"
    elif record_type == "exercise":
        record = Exercise.objects.create(
            user=other_user,
            exercise_type="running",
            duration_minutes=20,
            intensity="hard",
        )
        url = f"/exercises/{record.pk}/delete/"
    else:
        record = Measurement.objects.create(
            user=other_user, kind="waist", value=80
        )
        url = f"/measurements/{record.pk}/delete/"
    client.force_login(user)

    response = client.post(url)

    assert response.status_code == 404
    assert type(record).objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_strength_formset_rejects_another_users_hidden_child_id(
    client, user, other_user
):
    own_exercise = Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=30,
        intensity="moderate",
    )
    own_set = StrengthSet.objects.create(
        exercise=own_exercise,
        exercise_name="深蹲",
        sets=3,
        reps_per_set=8,
        order=0,
    )
    other_exercise = Exercise.objects.create(
        user=other_user,
        exercise_type="strength",
        duration_minutes=30,
        intensity="moderate",
    )
    other_set = StrengthSet.objects.create(
        exercise=other_exercise,
        exercise_name="卧推",
        sets=3,
        reps_per_set=8,
        order=0,
    )
    client.force_login(user)

    response = client.post(
        f"/exercises/{own_exercise.pk}/edit/",
        {
            "occurred_at": own_exercise.occurred_at.strftime("%Y-%m-%dT%H:%M"),
            "exercise_type": "strength",
            "duration_minutes": 30,
            "intensity": "moderate",
            "strength_sets-TOTAL_FORMS": 2,
            "strength_sets-INITIAL_FORMS": 1,
            "strength_sets-MIN_NUM_FORMS": 0,
            "strength_sets-MAX_NUM_FORMS": 20,
            "strength_sets-0-id": str(own_set.pk),
            "strength_sets-0-exercise_name": "深蹲",
            "strength_sets-0-sets": 3,
            "strength_sets-0-reps_per_set": 8,
            "strength_sets-0-order": 0,
            "strength_sets-1-id": str(other_set.pk),
            "strength_sets-1-exercise_name": "注入动作",
            "strength_sets-1-sets": 1,
            "strength_sets-1-reps_per_set": 1,
            "strength_sets-1-order": 1,
        },
    )

    assert response.status_code == 200
    assert list(
        own_exercise.strength_sets.values_list("exercise_name", flat=True)
    ) == ["深蹲"]
    other_set.refresh_from_db()
    assert other_set.exercise_name == "卧推"


@pytest.mark.django_db
def test_strength_formset_rejects_tampered_initial_count(client, user):
    exercise = Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=30,
        intensity="moderate",
    )
    for order in range(20):
        StrengthSet.objects.create(
            exercise=exercise,
            exercise_name=f"动作 {order}",
            sets=1,
            reps_per_set=1,
            order=order,
        )
    client.force_login(user)

    response = client.post(
        f"/exercises/{exercise.pk}/edit/",
        {
            "occurred_at": exercise.occurred_at.strftime("%Y-%m-%dT%H:%M"),
            "exercise_type": "strength",
            "duration_minutes": 30,
            "intensity": "moderate",
            "strength_sets-TOTAL_FORMS": 1,
            "strength_sets-INITIAL_FORMS": 0,
            "strength_sets-MIN_NUM_FORMS": 0,
            "strength_sets-MAX_NUM_FORMS": 20,
            "strength_sets-0-exercise_name": "第 21 条",
            "strength_sets-0-sets": 1,
            "strength_sets-0-reps_per_set": 1,
            "strength_sets-0-order": 20,
        },
    )

    assert response.status_code == 200
    assert exercise.strength_sets.count() == 20


@pytest.mark.django_db
def test_delete_confirmation_is_owner_scoped(client, user, other_user):
    meal = Meal.objects.create(
        user=other_user, meal_type="dinner", food="他人的晚餐"
    )
    client.force_login(user)

    response = client.get(f"/meals/{meal.pk}/delete/confirm/")

    assert response.status_code == 404
