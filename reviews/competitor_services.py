from decimal import Decimal

from django.db.models import Avg, Count, Q

from .models import Review, CompetitorPlatform
from .serializers import CompetitorSerializer


def _infer_platform(app_id, project=None, platform_lookup=None):
    """Return the canonical platform code for a known app identifier."""
    if not app_id:
        return None

    if platform_lookup:
        platform = platform_lookup.get(app_id)
        if platform:
            return platform.platform

    if project:
        if app_id == getattr(project, 'home_app_id', None):
            home_platform = getattr(project, 'home_platform', None)
            if home_platform in {'ios', 'android'}:
                return home_platform

        platform = project.get_competitor_platform(app_id)
        if platform:
            return platform.platform

    platform_code = (
        CompetitorPlatform.objects.filter(app_id=app_id)
        .values_list('platform', flat=True)
        .first()
    )
    if platform_code in {'ios', 'android'}:
        return platform_code

    source = (
        Review.objects.filter(app_id=app_id)
        .exclude(source__isnull=True)
        .values_list('source', flat=True)
        .first()
    )
    if source:
        normalized = source.lower()
        if 'apple' in normalized or 'ios' in normalized:
            return 'ios'
        if 'google' in normalized or 'android' in normalized:
            return 'android'

    return None


def _platform_label(code):
    return 'Android' if code == 'android' else 'iOS'


def _empty_metrics():
    return {
        'total_reviews': 0,
        'avg_sentiment': 0.0,
        'positive_reviews': 0,
        'negative_reviews': 0,
        'neutral_reviews': 0,
        'positive_percentage': 0.0,
        'negative_percentage': 0.0,
        'neutral_percentage': 0.0,
}


def _apply_percentages(stats):
    total = stats['total_reviews']
    if total:
        stats['positive_percentage'] = round((stats['positive_reviews'] / total) * 100, 2)
        stats['negative_percentage'] = round((stats['negative_reviews'] / total) * 100, 2)
        stats['neutral_percentage'] = round((stats['neutral_reviews'] / total) * 100, 2)
    else:
        stats['positive_percentage'] = 0.0
        stats['negative_percentage'] = 0.0
        stats['neutral_percentage'] = 0.0
    return stats


def _normalize_stats(stats):
    """Coerce stats to consistent numeric types for serialization."""
    total_reviews = int(stats.get('total_reviews') or 0)
    positive_reviews = int(stats.get('positive_reviews') or 0)
    negative_reviews = int(stats.get('negative_reviews') or 0)
    neutral_reviews = int(stats.get('neutral_reviews') or 0)

    avg_sentiment = stats.get('avg_sentiment', 0.0) or 0.0
    positive_percentage = stats.get('positive_percentage', 0.0) or 0.0
    negative_percentage = stats.get('negative_percentage', 0.0) or 0.0
    neutral_percentage = stats.get('neutral_percentage', 0.0) or 0.0

    return {
        'total_reviews': total_reviews,
        'avg_sentiment': round(float(avg_sentiment), 4),
        'positive_reviews': positive_reviews,
        'negative_reviews': negative_reviews,
        'neutral_reviews': neutral_reviews,
        'positive_percentage': round(float(positive_percentage), 2),
        'negative_percentage': round(float(negative_percentage), 2),
        'neutral_percentage': round(float(neutral_percentage), 2),
    }


def build_competitor_payload(project):
    competitors_qs = project.competitors.prefetch_related('platforms').order_by('display_name')

    platform_by_app_id = {}
    app_ids = {project.home_app_id}
    for competitor in competitors_qs:
        for platform in competitor.platforms.all():
            app_ids.add(platform.app_id)
            platform_by_app_id[platform.app_id] = platform

    metrics_qs = (
        Review.objects.filter(app_id__in=app_ids, sentiment_score__isnull=False)
        .values('app_id')
        .annotate(
            total=Count('id'),
            avg_sentiment=Avg('sentiment_score'),
            positive=Count('id', filter=Q(sentiment_score__gt=0.1)),
            negative=Count('id', filter=Q(sentiment_score__lt=-0.1)),
        )
    )

    platform_metrics = {app_id: _empty_metrics() for app_id in app_ids}

    for row in metrics_qs:
        stats = _empty_metrics()
        total = row['total']
        positive = row['positive']
        negative = row['negative']
        neutral = total - positive - negative
        avg_sentiment = row['avg_sentiment']
        if avg_sentiment is None:
            avg_sentiment = 0.0
        elif isinstance(avg_sentiment, Decimal):
            avg_sentiment = float(avg_sentiment)

        stats.update({
            'total_reviews': total,
            'avg_sentiment': round(avg_sentiment, 4),
            'positive_reviews': positive,
            'negative_reviews': negative,
            'neutral_reviews': neutral,
        })
        platform_metrics[row['app_id']] = _apply_percentages(stats)

    combined_metrics = {}
    for competitor in competitors_qs:
        combined = _empty_metrics()
        sentiment_sum = 0.0

        for platform in competitor.platforms.all():
            stats = platform_metrics.get(platform.app_id, _empty_metrics())
            combined['total_reviews'] += stats['total_reviews']
            combined['positive_reviews'] += stats['positive_reviews']
            combined['negative_reviews'] += stats['negative_reviews']
            combined['neutral_reviews'] += stats['neutral_reviews']
            sentiment_sum += stats['avg_sentiment'] * stats['total_reviews']

        total = combined['total_reviews']
        if total:
            combined['avg_sentiment'] = round(sentiment_sum / total, 4)
        combined_metrics[competitor.id] = _apply_percentages(combined)

    normalized_platform_metrics = {
        app_id: _normalize_stats(metrics)
        for app_id, metrics in platform_metrics.items()
    }

    normalized_combined_metrics = {
        comp_id: _normalize_stats(metrics)
        for comp_id, metrics in combined_metrics.items()
    }

    serializer_context = {
        'platform_metrics': normalized_platform_metrics,
        'combined_metrics': normalized_combined_metrics,
    }

    competitors_payload = CompetitorSerializer(
        competitors_qs,
        many=True,
        context=serializer_context,
    ).data

    home_metrics = normalized_platform_metrics.get(project.home_app_id, _empty_metrics())
    home_platform = _infer_platform(
        project.home_app_id,
        project=project,
        platform_lookup=platform_by_app_id,
    ) or 'android'
    home_stats = _normalize_stats(home_metrics)
    home_payload = {
        'app_id': project.home_app_id,
        'app_name': project.home_app_name,
        'display_name': project.home_app_name,
        'app_type': 'home',
        'stats': {
            'total_reviews': home_stats['total_reviews'],
            'avg_sentiment': home_stats['avg_sentiment'],
            'positive_reviews': home_stats['positive_reviews'],
            'negative_reviews': home_stats['negative_reviews'],
            'neutral_reviews': home_stats['neutral_reviews'],
            'positive_percentage': home_stats['positive_percentage'],
            'negative_percentage': home_stats['negative_percentage'],
            'neutral_percentage': home_stats['neutral_percentage'],
        },
        'platforms': [
            {
                'id': None,
                'platform_name': _platform_label(home_platform),
                'platform_label': _platform_label(home_platform),
                'platform': home_platform,
                'app_id': project.home_app_id,
                'stats': {
                    'reviews': home_stats['total_reviews'],
                    'sentiment': home_stats['avg_sentiment'],
                    'positive_reviews': home_stats['positive_reviews'],
                    'negative_reviews': home_stats['negative_reviews'],
                    'neutral_reviews': home_stats['neutral_reviews'],
                    'positive_percentage': home_stats['positive_percentage'],
                    'negative_percentage': home_stats['negative_percentage'],
                    'neutral_percentage': home_stats['neutral_percentage'],
                },
            }
        ],
    }

    competitor_analysis = {
        project.home_app_id: {
            'app_name': project.home_app_name,
            'display_name': project.home_app_name,
            'app_type': 'home',
            'total_reviews': home_stats['total_reviews'],
            'positive_count': home_stats['positive_reviews'],
            'negative_count': home_stats['negative_reviews'],
            'neutral_count': home_stats['neutral_reviews'],
            'positive_percentage': home_stats['positive_percentage'],
            'negative_percentage': home_stats['negative_percentage'],
            'neutral_percentage': home_stats['neutral_percentage'],
            'platform': home_platform,
            'platform_label': _platform_label(home_platform),
        }
    }

    for competitor in competitors_qs:
        for platform in competitor.platforms.all():
            stats = normalized_platform_metrics.get(platform.app_id, _empty_metrics())
            competitor_analysis[platform.app_id] = {
                'app_name': platform.app_name,
                'display_name': platform.app_name,
                'app_type': 'competitor',
                'total_reviews': stats['total_reviews'],
                'positive_count': stats['positive_reviews'],
                'negative_count': stats['negative_reviews'],
                'neutral_count': stats['neutral_reviews'],
                'positive_percentage': stats['positive_percentage'],
                'negative_percentage': stats['negative_percentage'],
                'neutral_percentage': stats['neutral_percentage'],
                'platform': platform.platform,
                'platform_label': platform.get_platform_display(),
            }

    return {
        'competitors_qs': competitors_qs,
        'competitors': competitors_payload,
        'home_card': home_payload,
        'competitor_analysis': competitor_analysis,
        'platform_metrics': normalized_platform_metrics,
        'platform_by_app': platform_by_app_id,
    }
