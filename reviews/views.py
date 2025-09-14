# file: reviews/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .tasks import extract_pain_points
from rest_framework import generics
from .models import Review
from .serializers import ReviewSerializer

class ReviewListView(generics.ListAPIView):
    queryset = Review.objects.all().order_by('-created_at') # Get all reviews, newest first
    serializer_class = ReviewSerializer


@api_view(['GET'])
def insights_summary(request):
    """
    API endpoint that returns business insights instead of raw reviews.
    This is what transforms Deepfocal from a review aggregator to a BI tool.
    """
    # Get pain points
    pain_points = extract_pain_points()

    # Get basic metrics
    total_reviews = Review.objects.filter(sentiment_score__isnull=False).count()
    negative_reviews = Review.objects.filter(sentiment_score__lt=-0.1).count()
    positive_reviews = Review.objects.filter(sentiment_score__gt=0.1).count()

    # Calculate percentages
    negative_percentage = round((negative_reviews / total_reviews * 100), 1) if total_reviews > 0 else 0
    positive_percentage = round((positive_reviews / total_reviews * 100), 1) if total_reviews > 0 else 0

    return Response({
        'total_reviews_analyzed': total_reviews,
        'sentiment_breakdown': {
            'positive_percentage': positive_percentage,
            'negative_percentage': negative_percentage,
            'positive_count': positive_reviews,
            'negative_count': negative_reviews
        },
        'top_pain_points': [
            {
                'issue': category.replace('_', ' ').title(),
                'mentions': count,
                'percentage_of_negative': round((count / negative_reviews * 100), 1) if negative_reviews > 0 else 0
            }
            for category, count in pain_points
        ]
    })


@api_view(['GET'])
def competitor_analysis(request):
    """
    Compare sentiment and pain points across different apps.
    This is the 'voice of the market' feature that differentiates Deepfocal.
    """
    from collections import defaultdict
    from .tasks import extract_pain_points

    # Get reviews grouped by app
    apps_data = defaultdict(lambda: {'total': 0, 'positive': 0, 'negative': 0, 'pain_points': []})

    # Analyze each app that has an app_id
    app_ids = Review.objects.filter(app_id__isnull=False).values_list('app_id', flat=True).distinct()

    for app_id in app_ids:
        app_reviews = Review.objects.filter(app_id=app_id, sentiment_score__isnull=False)
        total = app_reviews.count()
        positive = app_reviews.filter(sentiment_score__gt=0.1).count()
        negative = app_reviews.filter(sentiment_score__lt=-0.1).count()

        apps_data[app_id] = {
            'total_reviews': total,
            'positive_count': positive,
            'negative_count': negative,
            'positive_percentage': round((positive / total * 100), 1) if total > 0 else 0,
            'negative_percentage': round((negative / total * 100), 1) if total > 0 else 0,
        }

    return Response({
        'competitor_analysis': dict(apps_data),
        'market_insight': f"Analyzed {len(app_ids)} apps with {sum(data['total_reviews'] for data in apps_data.values())} total reviews"
    })