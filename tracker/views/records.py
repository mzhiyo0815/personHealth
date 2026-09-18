from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from tracker.forms import ExerciseForm, MealForm, MeasurementForm, StrengthSetFormSet


@login_required
def meal_create(request):
    form = MealForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        meal = form.save(commit=False)
        meal.user = request.user
        meal.save()
        return redirect("tracker:today")
    return render(request, "tracker/record_form.html", {"form": form, "title": "记录饮食"})


@login_required
def meal_edit(request, pk):
    meal = get_object_or_404(request.user.meals, pk=pk)
    form = MealForm(request.POST or None, instance=meal)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("tracker:today")
    return render(request, "tracker/record_form.html", {"form": form, "title": "编辑饮食"})


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
    form = ExerciseForm(request.POST or None)
    formset = StrengthSetFormSet(request.POST or None, instance=exercise, prefix="strength_sets")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            exercise = form.save(commit=False)
            exercise.user = request.user
            exercise.save()
            formset.instance = exercise
            formset.save()
        return redirect("tracker:today")
    return render(
        request,
        "tracker/record_form.html",
        {"form": form, "formset": formset, "title": "记录运动"},
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
                return redirect("tracker:today")
    else:
        exercise = get_object_or_404(request.user.exercises, pk=pk)
        form = ExerciseForm(instance=exercise)
        formset = StrengthSetFormSet(instance=exercise, prefix="strength_sets")
    return render(
        request,
        "tracker/record_form.html",
        {"form": form, "formset": formset, "title": "编辑运动"},
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
        return redirect("tracker:today")
    return render(
        request, "tracker/record_form.html", {"form": form, "title": "记录身体指标"}
    )


@login_required
def measurement_edit(request, pk):
    measurement = get_object_or_404(request.user.measurements, pk=pk)
    form = MeasurementForm(request.POST or None, instance=measurement)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("tracker:today")
    return render(
        request, "tracker/record_form.html", {"form": form, "title": "编辑身体指标"}
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
