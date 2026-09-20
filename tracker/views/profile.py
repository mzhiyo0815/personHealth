import csv

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator

from tracker.forms import LocalizedPasswordChangeForm, UserGoalForm
from tracker.models import UserGoal
from tracker.services.export import csv_export_rows, json_export_chunks, safe_csv_value


@login_required
def profile(request):
    goal = UserGoal.objects.filter(user=request.user).first() or UserGoal(user=request.user)
    form = UserGoalForm(request.POST if request.method == "POST" else None, instance=goal)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("tracker:profile")
    return render(request, "tracker/profile.html", {"form": form})


@method_decorator(login_required, name="dispatch")
class UserPasswordChangeView(PasswordChangeView):
    template_name = "tracker/password_change.html"
    form_class = LocalizedPasswordChangeForm
    success_url = reverse_lazy("tracker:profile")


@login_required
def export_json(request):
    return StreamingHttpResponse(
        json_export_chunks(request.user), content_type="application/json; charset=utf-8"
    )


@login_required
def export_csv(request):
    fieldnames = [
        "record_type", "phone", "id", "parent_id", "occurred_at", "meal_type", "food", "portion",
        "fullness", "calories", "protein", "carbohydrates", "fat",
        "exercise_type", "duration_minutes", "intensity", "notes",
        "exercise_name", "sets", "reps_per_set", "load_kg", "order", "kind", "value",
        "target_weight", "weekly_exercise_minutes", "weekly_strength_sessions", "show_calories",
    ]
    class Echo:
        def write(self, value):
            return value

    writer = csv.DictWriter(Echo(), fieldnames=fieldnames, extrasaction="ignore")

    def chunks():
        yield "\ufeff" + writer.writeheader()
        for row in csv_export_rows(request.user):
            yield writer.writerow({key: safe_csv_value(value) for key, value in row.items()})

    response = StreamingHttpResponse(chunks(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="health-data.csv"'
    return response
