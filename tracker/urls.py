from django.urls import path

from tracker.views import dashboard, history, profile, trends
from tracker.views import records

app_name = "tracker"

urlpatterns = [
    path("", dashboard.today, name="today"),
    path("history/", history.history, name="history"),
    path("trends/", trends.trends, name="trends"),
    path("me/", profile.profile, name="profile"),
    path("me/password/", profile.UserPasswordChangeView.as_view(), name="password-change"),
    path("me/export.json", profile.export_json, name="export-json"),
    path("me/export.csv", profile.export_csv, name="export-csv"),
    path("meals/new/", records.meal_create, name="meal-create"),
    path("meals/<uuid:pk>/edit/", records.meal_edit, name="meal-edit"),
    path(
        "meals/<uuid:pk>/delete/confirm/",
        records.meal_delete_confirm,
        name="meal-delete-confirm",
    ),
    path("meals/<uuid:pk>/delete/", records.meal_delete, name="meal-delete"),
    path("exercises/new/", records.exercise_create, name="exercise-create"),
    path("exercises/<uuid:pk>/edit/", records.exercise_edit, name="exercise-edit"),
    path(
        "exercises/<uuid:pk>/delete/confirm/",
        records.exercise_delete_confirm,
        name="exercise-delete-confirm",
    ),
    path(
        "exercises/<uuid:pk>/delete/",
        records.exercise_delete,
        name="exercise-delete",
    ),
    path("measurements/new/", records.measurement_create, name="measurement-create"),
    path(
        "measurements/<uuid:pk>/edit/",
        records.measurement_edit,
        name="measurement-edit",
    ),
    path(
        "measurements/<uuid:pk>/delete/confirm/",
        records.measurement_delete_confirm,
        name="measurement-delete-confirm",
    ),
    path(
        "measurements/<uuid:pk>/delete/",
        records.measurement_delete,
        name="measurement-delete",
    ),
]
