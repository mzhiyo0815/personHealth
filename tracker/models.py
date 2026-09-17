import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserGoal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goal"
    )
    target_weight = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0.01)],
    )
    weekly_exercise_minutes = models.PositiveIntegerField(default=150)
    weekly_strength_sessions = models.PositiveSmallIntegerField(default=2)
    show_calories = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OwnedTimedRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Meal(OwnedTimedRecord):
    class Type(models.TextChoices):
        BREAKFAST = "breakfast", "早餐"
        LUNCH = "lunch", "午餐"
        DINNER = "dinner", "晚餐"
        SNACK = "snack", "加餐"

    meal_type = models.CharField(max_length=16, choices=Type.choices)
    food = models.TextField()
    portion = models.CharField(max_length=200, blank=True)
    fullness = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    calories = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    protein = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    carbohydrates = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    fat = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    photo_url = models.URLField(blank=True)

    class Meta:
        indexes = [models.Index(fields=("user", "occurred_at"))]
        ordering = ("-occurred_at", "-created_at")


class Exercise(OwnedTimedRecord):
    class Type(models.TextChoices):
        WALKING = "walking", "快走"
        RUNNING = "running", "跑步"
        STRENGTH = "strength", "力量训练"
        OTHER = "other", "其他"

    class Intensity(models.TextChoices):
        EASY = "easy", "轻松"
        MODERATE = "moderate", "中等"
        HARD = "hard", "较累"

    exercise_type = models.CharField(max_length=16, choices=Type.choices)
    duration_minutes = models.PositiveIntegerField()
    intensity = models.CharField(max_length=16, choices=Intensity.choices)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=("user", "occurred_at"))]
        ordering = ("-occurred_at", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0),
                name="exercise_duration_positive",
            )
        ]


class StrengthSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name="strength_sets"
    )
    exercise_name = models.CharField(max_length=120)
    sets = models.PositiveSmallIntegerField()
    reps_per_set = models.PositiveSmallIntegerField()
    load_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("exercise", "order")
        constraints = [
            models.CheckConstraint(condition=Q(sets__gt=0), name="strength_sets_positive"),
            models.CheckConstraint(
                condition=Q(reps_per_set__gt=0), name="strength_reps_positive"
            ),
        ]


class Measurement(OwnedTimedRecord):
    class Kind(models.TextChoices):
        WEIGHT = "weight", "体重"
        WAIST = "waist", "腰围"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    value = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        indexes = [models.Index(fields=("user", "occurred_at"))]
        ordering = ("-occurred_at", "-created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(value__gt=0), name="measurement_value_positive"
            )
        ]
