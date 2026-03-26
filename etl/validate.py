from __future__ import annotations


REQUIRED_FIELDS = [
    "article_id",
    "category",
    "title",
    "url",
]


def validate_news(**context):
    transformed_news = context["ti"].xcom_pull(task_ids="transform_news", key="transformed_news") or []
    valid_items = []

    for item in transformed_news:
        if all(item.get(field) for field in REQUIRED_FIELDS):
            valid_items.append(item)

    context["ti"].xcom_push(key="validated_news", value=valid_items)
    return valid_items
