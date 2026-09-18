from django import forms
from django.forms.models import BaseInlineFormSet

from .models import Exercise, Meal, Measurement, StrengthSet, UserGoal


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class MealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = (
            "occurred_at",
            "meal_type",
            "food",
            "portion",
            "fullness",
            "calories",
            "protein",
            "carbohydrates",
            "fat",
        )
        widgets = {
            "occurred_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "fullness": forms.NumberInput(attrs={"min": 1, "max": 10}),
            "calories": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "protein": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "carbohydrates": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "fat": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occurred_at"].input_formats = ["%Y-%m-%dT%H:%M"]


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = (
            "occurred_at",
            "exercise_type",
            "duration_minutes",
            "intensity",
            "notes",
        )
        widgets = {
            "occurred_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "duration_minutes": forms.NumberInput(attrs={"min": 1, "max": 1440}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occurred_at"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]
        if duration > 1440:
            raise forms.ValidationError("运动时长不能超过 1440 分钟。")
        return duration


class StrengthSetForm(forms.ModelForm):
    class Meta:
        model = StrengthSet
        fields = ("exercise_name", "sets", "reps_per_set", "load_kg", "order")
        widgets = {
            "sets": forms.NumberInput(attrs={"min": 1}),
            "reps_per_set": forms.NumberInput(attrs={"min": 1}),
            "load_kg": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "order": forms.HiddenInput(),
        }


class BaseStrengthSetFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        allowed_ids = set()
        if self.instance.pk:
            allowed_ids = set(
                self.instance.strength_sets.values_list("pk", flat=True)
            )
        initial_count = self.initial_form_count()
        if initial_count != len(allowed_ids):
            raise forms.ValidationError("力量训练明细已变化，请刷新后重试。")

        submitted_initial_ids = []
        for index, form in enumerate(self.forms):
            child = form.cleaned_data.get("id")
            if index < initial_count:
                if child is None or child.pk not in allowed_ids:
                    raise forms.ValidationError("力量训练明细无效，请刷新后重试。")
                submitted_initial_ids.append(child.pk)
            elif child is not None:
                raise forms.ValidationError("力量训练明细无效，请刷新后重试。")

        if set(submitted_initial_ids) != allowed_ids:
            raise forms.ValidationError("力量训练明细无效，请刷新后重试。")

        deleted_count = sum(
            bool(form.cleaned_data.get("DELETE"))
            for form in self.forms[:initial_count]
        )
        new_count = sum(
            form.has_changed() and not form.cleaned_data.get("DELETE")
            for form in self.forms[initial_count:]
        )
        if len(allowed_ids) - deleted_count + new_count > 20:
            raise forms.ValidationError("力量训练明细不能超过 20 条。")


StrengthSetFormSet = forms.inlineformset_factory(
    Exercise,
    StrengthSet,
    form=StrengthSetForm,
    formset=BaseStrengthSetFormSet,
    extra=1,
    can_delete=True,
    max_num=20,
    validate_max=True,
)


class MeasurementForm(forms.ModelForm):
    class Meta:
        model = Measurement
        fields = ("occurred_at", "kind", "value")
        widgets = {
            "occurred_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "value": forms.NumberInput(attrs={"min": 0.01, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occurred_at"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean(self):
        cleaned_data = super().clean()
        kind = cleaned_data.get("kind")
        value = cleaned_data.get("value")
        limits = {Measurement.Kind.WEIGHT: 500, Measurement.Kind.WAIST: 300}
        if kind in limits and value is not None and value > limits[kind]:
            self.add_error("value", f"数值不能超过 {limits[kind]}。")
        return cleaned_data


class UserGoalForm(forms.ModelForm):
    class Meta:
        model = UserGoal
        fields = (
            "target_weight",
            "weekly_exercise_minutes",
            "weekly_strength_sessions",
            "show_calories",
        )
        widgets = {
            "target_weight": forms.NumberInput(attrs={"min": 0.01, "max": 500, "step": "0.01"}),
            "weekly_exercise_minutes": forms.NumberInput(attrs={"min": 0}),
            "weekly_strength_sessions": forms.NumberInput(attrs={"min": 0}),
        }

    def clean_target_weight(self):
        value = self.cleaned_data.get("target_weight")
        if value is not None and value > 500:
            raise forms.ValidationError("目标体重不能超过 500 kg。")
        return value

    def clean_weekly_exercise_minutes(self):
        value = self.cleaned_data["weekly_exercise_minutes"]
        if value > 10080:
            raise forms.ValidationError("每周运动目标不能超过 10080 分钟。")
        return value

    def clean_weekly_strength_sessions(self):
        value = self.cleaned_data["weekly_strength_sessions"]
        if value > 100:
            raise forms.ValidationError("每周力量训练目标不能超过 100 次。")
        return value
