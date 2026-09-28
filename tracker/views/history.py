from collections import defaultdict
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from tracker.forms import HistoryFilterForm
from tracker.views.dashboard import local_day_bounds


@login_required
def history(request):
    filter_form = HistoryFilterForm(request.GET)
    filter_valid = filter_form.is_valid()
    has_filters = False
    querysets = ()

    if filter_valid:
        start_date = filter_form.cleaned_data["start_date"]
        end_date = filter_form.cleaned_data["end_date"]
        record_type = filter_form.cleaned_data["record_type"]
        keyword = filter_form.cleaned_data["keyword"]
        has_filters = bool(
            start_date or end_date or record_type != "all" or keyword
        )

        meals = request.user.meals.all()
        exercises = request.user.exercises.all()
        measurements = request.user.measurements.all()
        if start_date:
            start, _ = local_day_bounds(start_date)
            meals = meals.filter(occurred_at__gte=start)
            exercises = exercises.filter(occurred_at__gte=start)
            measurements = measurements.filter(occurred_at__gte=start)
        if end_date:
            _, end = local_day_bounds(end_date)
            meals = meals.filter(occurred_at__lt=end)
            exercises = exercises.filter(occurred_at__lt=end)
            measurements = measurements.filter(occurred_at__lt=end)
        if keyword:
            meals = meals.filter(
                Q(food__icontains=keyword) | Q(portion__icontains=keyword)
            )
            exercises = exercises.filter(notes__icontains=keyword)
            measurements = measurements.none()

        if record_type == "all":
            querysets = (
                ("meal", meals),
                ("exercise", exercises),
                ("measurement", measurements),
            )
        elif record_type == "meal":
            querysets = (("meal", meals),)
        elif record_type == "exercise":
            querysets = (("exercise", exercises),)
        else:
            querysets = (
                ("measurement", measurements.filter(kind=record_type)),
            )

    if querysets:
        current_timezone = timezone.get_current_timezone()
        date_queries = [
            queryset.annotate(
                local_day=TruncDate("occurred_at", tzinfo=current_timezone)
            )
            .values_list("local_day", flat=True)
            .order_by()
            for _, queryset in querysets
        ]
        day_source = date_queries[0]
        if len(date_queries) > 1:
            day_source = day_source.union(*date_queries[1:])
        day_source = day_source.order_by("-local_day")
    else:
        day_source = []

    page = Paginator(day_source, 7).get_page(request.GET.get("page"))
    page_days = list(page.object_list)
    grouped = defaultdict(list)
    if page_days:
        start, _ = local_day_bounds(min(page_days))
        _, end = local_day_bounds(max(page_days))
        for record_type, queryset in querysets:
            if record_type == "exercise":
                queryset = queryset.prefetch_related("strength_sets")
            for record in queryset.filter(
                occurred_at__gte=start, occurred_at__lt=end
            ):
                record.record_type = record_type
                local_date = timezone.localtime(record.occurred_at).date()
                if local_date in page_days:
                    grouped[local_date].append(record)

    page.object_list = [
        {
            "date": day,
            "records": sorted(
                grouped[day], key=lambda row: row.occurred_at, reverse=True
            ),
        }
        for day in page_days
    ]
    filter_params = {}
    if filter_valid:
        for name in ("start_date", "end_date", "record_type", "keyword"):
            value = filter_form.cleaned_data[name]
            if value and value != "all":
                filter_params[name] = value.isoformat() if name.endswith("date") else value
    return render(
        request,
        "tracker/history.html",
        {
            "page": page,
            "filter_form": filter_form,
            "filter_query": urlencode(filter_params),
            "has_filters": has_filters,
            "filter_valid": filter_valid,
        },
    )
