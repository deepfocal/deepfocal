"""Dashboard analytics helpers for premium UI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Iterable, List, Optional

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDay, TruncWeek
from django.utils import timezone

from .models import CompetitorApp, Project, Review
from .app_id_utils import expand_app_ids, expand_many_app_ids


@dataclass
class SentimentBucket:
    date_label: str
    positive: float
    negative: float
    competitor: Optional[float] = None


def _bounded(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _project_home_ids(project: Project) -> List[str]:
    return [app_id for app_id in {project.home_app_id, project.apple_app_id} if app_id]


def _competitor_app_ids(project: Project, identifier: str | None) -> List[str]:
    if not identifier:
        return []
    competitor = project.competitors.filter(
        Q(app_id=identifier) | Q(apple_app_id=identifier)
    ).first()
    if competitor:
        return [app_id for app_id in {competitor.app_id, competitor.apple_app_id} if app_id]
    return expand_app_ids(identifier)


def calculate_strategic_scores(project: Project) -> Dict[str, float]:
    """Derive MVP strategic metrics from review sentiment data."""
    home_ids = _project_home_ids(project)
    home_stats = _aggregate_sentiment_metrics(home_ids)

    competitor_records = list(CompetitorApp.objects.filter(project=project).only(
        "app_id", "apple_app_id"
    ))
    competitor_ids: List[str] = []
    for competitor in competitor_records:
        if competitor.app_id:
            competitor_ids.append(competitor.app_id)
        if competitor.apple_app_id:
            competitor_ids.append(competitor.apple_app_id)
    competitor_stats = _aggregate_sentiment_metrics(competitor_ids) if competitor_ids else None

    positive_pct = home_stats.get("positive_percentage", 0.0)
    churn_risk = _bounded(100.0 - (positive_pct * 1.2))

    your_sentiment = home_stats.get("avg_sentiment", 0.0)
    competitor_avg_sentiment = (
        competitor_stats.get("avg_sentiment", 0.0) if competitor_stats else 0.0
    )
    competitive_delta = competitor_avg_sentiment - your_sentiment
    competitive_gap = _bounded(((competitive_delta + 1.0) / 2.0) * 100.0)

    return {
        "churn_risk_score": round(churn_risk, 1),
        "competitive_gap_score": round(competitive_gap, 1),
        "category_ranking": {
            "label": "#27 in Productivity",
            "trend": {
                "direction": "up",
                "delta": 2,
            },
        },
        "source": {
            "home": home_stats,
            "competitor": competitor_stats,
        },
    }

def _aggregate_sentiment_metrics(app_ids: Iterable[str]) -> Dict[str, float]:
    expanded_ids = expand_many_app_ids(app_ids)
    if not expanded_ids:
        return {
            "total_reviews": 0,
            "positive_percentage": 0.0,
            "negative_percentage": 0.0,
            "avg_sentiment": 0.0,
        }

    queryset = Review.objects.filter(
        app_id__in=expanded_ids,
        sentiment_score__isnull=False,
        counts_toward_score=True,
    )
    aggregated = queryset.aggregate(
        total=Count("id"),
        positive=Count("id", filter=Q(sentiment_score__gt=0.1)),
        negative=Count("id", filter=Q(sentiment_score__lt=-0.1)),
        avg_sentiment=Avg("sentiment_score"),
    )

    total = aggregated.get("total") or 0
    positive = aggregated.get("positive") or 0
    negative = aggregated.get("negative") or 0
    neutral = max(total - positive - negative, 0)

    def pct(part: int) -> float:
        return round((part / total) * 100.0, 1) if total else 0.0

    return {
        "total_reviews": total,
        "positive_reviews": positive,
        "negative_reviews": negative,
        "neutral_reviews": neutral,
        "positive_percentage": pct(positive),
        "negative_percentage": pct(negative),
        "neutral_percentage": pct(neutral),
        "avg_sentiment": round(aggregated.get("avg_sentiment") or 0.0, 4),
    }

def build_sentiment_trend(
    project: Project,
    app_id: str,
    compare_app_id: Optional[str] = None,
    date_range: str = "30d",
) -> List[Dict[str, Optional[float]]]:
    """Return time-series sentiment data for charting."""
    horizon = _infer_horizon(date_range)
    since = timezone.now() - horizon

    home_ids = _project_home_ids(project)
    if app_id in home_ids or app_id == project.apple_app_id:
        target_home_ids = home_ids
    else:
        target_home_ids = expand_app_ids(app_id)
    home_series = _sentiment_series(target_home_ids, since)

    competitor_series = None
    competitor_ids: List[str] = []
    if compare_app_id:
        competitor_ids = _competitor_app_ids(project, compare_app_id)
        competitor_series = _sentiment_series(competitor_ids, since)

    if not home_series:
        home_series = _sentiment_series(target_home_ids, None)

    if compare_app_id and competitor_series is not None and not competitor_series:
        competitor_series = _sentiment_series(competitor_ids, None)

    buckets: Dict[str, SentimentBucket] = {}

    for bucket in home_series:
        buckets[bucket["label"]] = SentimentBucket(
            date_label=bucket["label"],
            positive=bucket["positive"],
            negative=bucket["negative"],
        )

    if competitor_series:
        for bucket in competitor_series:
            entry = buckets.setdefault(
                bucket["label"],
                SentimentBucket(bucket["label"], positive=0.0, negative=0.0),
            )
            entry.competitor = bucket["positive"]

    ordered = sorted(buckets.values(), key=lambda item: item.date_label)
    return [
        {
            "date": item.date_label,
            "positive": round(item.positive, 1),
            "negative": round(item.negative, 1),
            "competitor": round(item.competitor, 1) if item.competitor is not None else None,
        }
        for item in ordered
    ]



def _infer_horizon(date_range: str) -> timedelta:
    mapping = {
        "7d": timedelta(days=7),
        "14d": timedelta(days=14),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "180d": timedelta(days=180),
    }
    return mapping.get(date_range, timedelta(days=30))


def _sentiment_series(app_ids: Iterable[str], since) -> List[Dict[str, float]]:
    app_ids = [app_id for app_id in set(app_ids) if app_id]
    if not app_ids:
        return []

    filters = {
        'app_id__in': app_ids,
        'sentiment_score__isnull': False,
        'counts_toward_score': True,
        'source': 'Google Play',
    }

    if since is not None:
        filters['created_at__gte'] = since

    queryset = Review.objects.filter(**filters)

    if not queryset.exists():
        if since is None:
            return []
        queryset = Review.objects.filter(
            app_id__in=app_ids,
            sentiment_score__isnull=False,
            counts_toward_score=True,
            source='Google Play',
        )
        if not queryset.exists():
            return []
        since = queryset.order_by('created_at').first().created_at

    horizon = timezone.now() - since if since else timedelta.max
    truncate = TruncDay("created_at") if horizon <= timedelta(days=30) else TruncWeek("created_at")

    aggregated = (
        queryset.annotate(bucket=truncate)
        .values("bucket")
        .annotate(
            total=Count("id"),
            positive=Count("id", filter=Q(sentiment_score__gt=0.1)),
            negative=Count("id", filter=Q(sentiment_score__lt=-0.1)),
        )
        .order_by("bucket")
    )

    results: List[Dict[str, float]] = []
    for row in aggregated:
        total = row["total"] or 1
        label = row["bucket"].strftime("%b %d")
        results.append(
            {
                "label": label,
                "positive": (row["positive"] / total) * 100.0,
                "negative": (row["negative"] / total) * 100.0,
            }
        )
    return results

