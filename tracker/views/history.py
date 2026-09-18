from collections import defaultdict
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from tracker.views.dashboard import local_day_bounds


def parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@login_required
def history(request):
    selected_date = parse_date(request.GET.get("date"))
    querysets = (
        ("meal", request.user.meals.all()),
        ("exercise", request.user.exercises.all()),
        ("measurement", request.user.measurements.all()),
    )
    current_timezone = timezone.get_current_timezone()
    if selected_date:
        start, end = local_day_bounds(selected_date)
        has_records = any(
            queryset.filter(occurred_at__gte=start, occurred_at__lt=end).exists()
            for _, queryset in querysets
        )
        day_source = [selected_date] if has_records else []
    else:
        date_queries = [
            queryset.annotate(
                local_day=TruncDate("occurred_at", tzinfo=current_timezone)
            )
            .values_list("local_day", flat=True)
            .order_by()
            for _, queryset in querysets
        ]
        day_source = date_queries[0].union(*date_queries[1:]).order_by("-local_day")

    page = Paginator(day_source, 7).get_page(request.GET.get("page"))
    page_days = list(page.object_list)
    grouped = defaultdict(list)
    if page_days:
        start, _ = local_day_bounds(min(page_days))
        _, end = local_day_bounds(max(page_days))
        for record_type, queryset in querysets:
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
    return render(
        request,
        "tracker/history.html",
        {"page": page, "selected_date": selected_date},
    )
