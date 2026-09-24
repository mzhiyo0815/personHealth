import re
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from tracker.forms import ExerciseForm, MealForm, MeasurementForm, StrengthSetFormSet


DRAFT_TOKEN_RE = re.compile(
    r"\A[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)

MEAL_COPY_FIELDS = (
    "meal_type",
    "food",
    "portion",
    "fullness",
    "calories",
    "protein",
    "carbohydrates",
    "fat",
)
EXERCISE_COPY_FIELDS = (
    "exercise_type",
    "duration_minutes",
    "intensity",
    "notes",
)
STRENGTH_SET_COPY_FIELDS = (
    "exercise_name",
    "sets",
    "reps_per_set",
    "load_kg",
    "order",
)
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


def owned_copy_source_or_404(queryset, raw_pk):
    try:
        pk = UUID(raw_pk)
    except (AttributeError, TypeError, ValueError) as error:
        raise Http404 from error
    return get_object_or_404(queryset, pk=pk)


def redirect_after_save(request):
    token = request.POST.get("draft_token", "").lower()
    location = reverse("tracker:today")
    if DRAFT_TOKEN_RE.fullmatch(token):
        location = f"{location}?draft_saved={token}"
    return redirect(location)


@login_required
def meal_create(request):
    initial = {}
    copy_requested = request.method == "GET" and "copy" in request.GET
    if copy_requested:
        copy_pk = request.GET.get("copy")
        source = owned_copy_source_or_404(request.user.meals, copy_pk)
        initial = {field: getattr(source, field) for field in MEAL_COPY_FIELDS}
        initial["occurred_at"] = timezone.now()
    form = MealForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        meal = form.save(commit=False)
        meal.user = request.user
        meal.save()
        return redirect_after_save(request)
    return render(request, "tracker/record_form.html", record_form_context(form, "记录饮食", "meal"))


@login_required
def meal_edit(request, pk):
    meal = get_object_or_404(request.user.meals, pk=pk)
    form = MealForm(request.POST or None, instance=meal)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect_after_save(request)
    return render(request, "tracker/record_form.html", record_form_context(form, "编辑饮食", "meal"))


@login_required
def meal_delete_confirm(request, pk):
    meal = get_object_or_404(request.user.meals, pk=pk)
    return render(
        request,
        "tracker/confirm_delete.html",
        {"object": meal, "delete_url": "tracker:meal-delete"},
    )


@login_required
@require_POST
def meal_delete(request, pk):
    meal = get_object_or_404(request.user.meals, pk=pk)
    meal.delete()
    return redirect("tracker:today")


@login_required
def exercise_create(request):
    exercise = None
    initial = {}
    strength_initial = []
    copy_requested = request.method == "GET" and "copy" in request.GET
    if copy_requested:
        copy_pk = request.GET.get("copy")
        source = owned_copy_source_or_404(
            request.user.exercises.prefetch_related("strength_sets"), copy_pk
        )
        initial = {
            field: getattr(source, field) for field in EXERCISE_COPY_FIELDS
        }
        initial["occurred_at"] = timezone.now()
        strength_initial = [
            {field: getattr(strength_set, field) for field in STRENGTH_SET_COPY_FIELDS}
            for strength_set in source.strength_sets.all()
        ]
    form = ExerciseForm(request.POST or None, initial=initial)
    formset = StrengthSetFormSet(
        request.POST or None,
        instance=exercise,
        prefix="strength_sets",
        initial=strength_initial,
    )
    if request.method == "GET" and strength_initial:
        formset.extra = len(strength_initial)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            exercise = form.save(commit=False)
            exercise.user = request.user
            exercise.save()
            formset.instance = exercise
            formset.save()
        return redirect_after_save(request)
    return render(
        request,
        "tracker/record_form.html",
        record_form_context(form, "记录运动", "exercise", formset),
    )


@login_required
def exercise_edit(request, pk):
    if request.method == "POST":
        with transaction.atomic():
            exercise = get_object_or_404(
                request.user.exercises.select_for_update(), pk=pk
            )
            form = ExerciseForm(request.POST, instance=exercise)
            formset = StrengthSetFormSet(
                request.POST, instance=exercise, prefix="strength_sets"
            )
            if form.is_valid() and formset.is_valid():
                form.save()
                formset.save()
                return redirect_after_save(request)
    else:
        exercise = get_object_or_404(request.user.exercises, pk=pk)
        form = ExerciseForm(instance=exercise)
        formset = StrengthSetFormSet(instance=exercise, prefix="strength_sets")
    return render(
        request,
        "tracker/record_form.html",
        record_form_context(form, "编辑运动", "exercise", formset),
    )


@login_required
def exercise_delete_confirm(request, pk):
    exercise = get_object_or_404(request.user.exercises, pk=pk)
    return render(
        request,
        "tracker/confirm_delete.html",
        {"object": exercise, "delete_url": "tracker:exercise-delete"},
    )


@login_required
@require_POST
def exercise_delete(request, pk):
    exercise = get_object_or_404(request.user.exercises, pk=pk)
    exercise.delete()
    return redirect("tracker:today")


@login_required
def measurement_create(request):
    initial = {}
    if request.GET.get("kind") in {"weight", "waist"}:
        initial["kind"] = request.GET["kind"]
    form = MeasurementForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        measurement = form.save(commit=False)
        measurement.user = request.user
        measurement.save()
        return redirect_after_save(request)
    return render(
        request, "tracker/record_form.html", record_form_context(form, "记录身体指标", "measurement")
    )


@login_required
def measurement_edit(request, pk):
    measurement = get_object_or_404(request.user.measurements, pk=pk)
    form = MeasurementForm(request.POST or None, instance=measurement)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect_after_save(request)
    return render(
        request, "tracker/record_form.html", record_form_context(form, "编辑身体指标", "measurement")
    )


@login_required
def measurement_delete_confirm(request, pk):
    measurement = get_object_or_404(request.user.measurements, pk=pk)
    return render(
        request,
        "tracker/confirm_delete.html",
        {"object": measurement, "delete_url": "tracker:measurement-delete"},
    )


@login_required
@require_POST
def measurement_delete(request, pk):
    measurement = get_object_or_404(request.user.measurements, pk=pk)
    measurement.delete()
    return redirect("tracker:today")
