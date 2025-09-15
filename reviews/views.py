# file: reviews/views.py
from .topic_modeling import analyze_app_topics
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
def enhanced_insights_summary(request):
    """
    Enhanced insights using LDA topic modeling instead of keyword matching
    """
    app_id = request.GET.get('app_id')  # Allow filtering by specific app

    # Get LDA-based pain points
    if app_id:
        lda_results = analyze_app_topics(app_id, sentiment_filter='negative')
        pain_points = []

        if 'topics' in lda_results:
            for topic in lda_results['topics'][:3]:  # Top 3 topics
                pain_points.append({
                    'issue': topic['label'],
                    'keywords': topic['top_words'][:5],
                    'coherence_score': topic['coherence_score']
                })

    # Return enhanced insights with LDA topics
    return Response({
        'lda_pain_points': pain_points,
        'review_count_analyzed': lda_results.get('review_count', 0),
        'app_id': app_id
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