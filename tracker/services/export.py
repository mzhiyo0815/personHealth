from django.core.serializers.json import DjangoJSONEncoder


def fields(row, names):
    return {name: getattr(row, name) for name in names}


def json_export_chunks(user):
    encoder = DjangoJSONEncoder(ensure_ascii=False)
    goal = user.goal if hasattr(user, "goal") else None
    yield encoder.encode({"phone": user.phone, "goal": fields(goal, (
        "target_weight", "weekly_exercise_minutes", "weekly_strength_sessions", "show_calories"
    )) if goal else None})[:-1]
    specs = (
        ("meals", user.meals.all(), ("id", "occurred_at", "meal_type", "food", "portion", "fullness", "calories", "protein", "carbohydrates", "fat")),
        ("exercises", user.exercises.prefetch_related("strength_sets"), ("id", "occurred_at", "exercise_type", "duration_minutes", "intensity", "notes")),
        ("measurements", user.measurements.all(), ("id", "occurred_at", "kind", "value")),
    )
    for key, queryset, names in specs:
        yield f', "{key}": ['
        first = True
        for row in queryset.iterator(chunk_size=200):
            item = fields(row, names)
            if key == "exercises":
                item["strength_sets"] = [fields(child, ("id", "exercise_name", "sets", "reps_per_set", "load_kg", "order")) for child in row.strength_sets.all()]
            yield ("" if first else ",") + encoder.encode(item)
            first = False
        yield "]"
    yield "}"


def safe_csv_value(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def csv_export_rows(user):
    yield {"record_type": "account", "phone": user.phone}
    if hasattr(user, "goal"):
        yield {"record_type": "goal", **fields(user.goal, ("target_weight", "weekly_exercise_minutes", "weekly_strength_sessions", "show_calories"))}
    for row in user.meals.all().iterator(chunk_size=200):
        yield {"record_type": "meal", **fields(row, ("id", "occurred_at", "meal_type", "food", "portion", "fullness", "calories", "protein", "carbohydrates", "fat"))}
    for row in user.exercises.prefetch_related("strength_sets").iterator(chunk_size=200):
        yield {"record_type": "exercise", **fields(row, ("id", "occurred_at", "exercise_type", "duration_minutes", "intensity", "notes"))}
        for child in row.strength_sets.all():
            yield {"record_type": "strength_set", "parent_id": row.id, **fields(child, ("id", "exercise_name", "sets", "reps_per_set", "load_kg", "order"))}
    for row in user.measurements.all().iterator(chunk_size=200):
        yield {"record_type": "measurement", **fields(row, ("id", "occurred_at", "kind", "value"))}
