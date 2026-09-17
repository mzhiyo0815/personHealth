import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from tracker.models import Exercise, Meal, Measurement, StrengthSet


@pytest.mark.django_db
def test_meal_allows_blank_nutrition(user):
    meal = Meal(
        user=user,
        meal_type="breakfast",
        food="鸡蛋和豆浆",
        portion="2 个、300 ml",
        fullness=7,
    )

    meal.full_clean()


@pytest.mark.django_db
def test_measurement_rejects_non_positive_value(user):
    item = Measurement(user=user, kind="weight", value=0)

    with pytest.raises(ValidationError):
        item.full_clean()


@pytest.mark.django_db
def test_records_have_owner_scoped_reverse_relations(user):
    Meal.objects.create(user=user, meal_type="lunch", food="米饭和蔬菜")
    Measurement.objects.create(user=user, kind="weight", value=70)
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=30,
        intensity="moderate",
    )

    assert user.meals.count() == 1
    assert user.measurements.count() == 1
    assert user.exercises.count() == 1


def test_strength_sets_are_ordered_by_exercise_then_order():
    assert StrengthSet._meta.ordering == ("exercise", "order")


@pytest.mark.django_db
def test_database_rejects_non_positive_record_values(user):
    exercise = Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=30,
        intensity="moderate",
    )

    invalid_rows = (
        lambda: Measurement.objects.create(user=user, kind="weight", value=0),
        lambda: Exercise.objects.create(
            user=user,
            exercise_type="walking",
            duration_minutes=0,
            intensity="easy",
        ),
        lambda: StrengthSet.objects.create(
            exercise=exercise,
            exercise_name="深蹲",
            sets=0,
            reps_per_set=8,
        ),
        lambda: StrengthSet.objects.create(
            exercise=exercise,
            exercise_name="深蹲",
            sets=3,
            reps_per_set=0,
        ),
    )

    for create_invalid_row in invalid_rows:
        with pytest.raises(IntegrityError), transaction.atomic():
            create_invalid_row()


@pytest.mark.django_db
def test_same_day_measurements_are_allowed(user):
    occurred_at = timezone.now()

    Measurement.objects.create(
        user=user, kind="weight", value=70, occurred_at=occurred_at
    )
    Measurement.objects.create(
        user=user, kind="weight", value=69.8, occurred_at=occurred_at
    )

    assert user.measurements.count() == 2
