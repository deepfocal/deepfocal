# file: reviews/views.py - Optimized version with caching and your existing project system
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from django.core.cache import cache
from django.db.models import Q, Count, Avg
from .models import Review, Project, CompetitorApp, UserProfile
from .serializers import ReviewSerializer
from .topic_modeling import analyze_app_topics
from .app_id_utils import expand_app_ids, expand_many_app_ids, get_reviews_for_app_id
from .tasks import import_google_play_reviews_for_user
from celery.result import AsyncResult
from datetime import datetime, timezone
import json
import hashlib


class ReviewListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        user = self.request.user
        projects = Project.objects.filter(user=user).prefetch_related('competitors')
        app_ids = set()
        for project in projects:
            home_ids = expand_many_app_ids([project.home_app_id, project.apple_app_id])
            app_ids.update(home_ids)
            for competitor in project.competitors.all():
                competitor_ids = expand_many_app_ids([competitor.app_id, competitor.apple_app_id])
                app_ids.update(competitor_ids)
        if not app_ids:
            return Review.objects.none()
        return Review.objects.filter(app_id__in=app_ids).order_by('-created_at')


@permission_classes([IsAuthenticated])
@api_view(['GET'])
def enhanced_insights_summary(request):
    """
    Enhanced insights using LDA topic modeling with caching
    """
    app_id = request.GET.get('app_id', None)

    if not app_id:
        return Response(
            {"error": "The 'app_id' query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    related_app_ids = expand_app_ids(app_id)
    if not related_app_ids:
        related_app_ids = [app_id]

    last_update = max((cache.get(f'last_data_update_{identifier}', 0) for identifier in related_app_ids), default=0)

    # Create cache key for this specific app's insights
    cache_key_data = {
        'endpoint': 'enhanced_insights',
        'app_id': app_id,
        'app_ids': related_app_ids,
        'timestamp': last_update,
        'schema_version': 2,
    }
    cache_key = hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()

    # Try to get from cache first
    cached_result = cache.get(f"enhanced_insights_{cache_key}")
    if cached_result:
        cached_result['cached'] = True
        return Response(cached_result)

    # If not cached, compute results
    lda_results = analyze_app_topics(app_id, sentiment_filter='negative')
    pain_points = []

    topic_examples = lda_results.get('topic_examples', {})
    topics_for_display = lda_results.get('distinct_topics') or lda_results.get('topics', [])

    if topics_for_display:
        for topic in topics_for_display[:3]:  # Top 3 distinct topics
            examples = topic_examples.get(topic['topic_id'], [])
            quotes = [example.get('quote', '').strip() for example in examples if example.get('quote')]

            pain_points.append({
                'issue': topic['label'],
                'keywords': topic['top_words'][:5],
                'coherence_score': topic['coherence_score'],
                'mentions': topic.get('mentions', 0),
                'review_percentage': topic.get('mention_percentage', 0),
                'average_probability': topic.get('average_probability', 0.0),
                'quotes': quotes
            })

    # Return enhanced insights with LDA topics
    review_count = lda_results.get('review_count', 0)
    raw_review_count = lda_results.get('raw_review_count', review_count)
    filtered_out = lda_results.get('filtered_out_reviews', max(raw_review_count - review_count, 0))

    result = {
        'lda_pain_points': pain_points,
        'review_count_analyzed': review_count,
        'raw_review_count': raw_review_count,
        'filtered_out_reviews': filtered_out,
        'app_id': app_id,
        'topic_stats': lda_results.get('topic_stats', {}),
        'combined_app_ids': related_app_ids,
        'cached': False
    }

    # Cache for 1 hour
    cache.set(f"enhanced_insights_{cache_key}", result, 3600)

    return Response(result)




@permission_classes([IsAuthenticated])
@api_view(['GET'])
def market_mentions(request):
    """Return voice-of-the-market signals from non-store sources (web, Reddit, etc.)."""
    app_id = request.query_params.get('app_id')
    if not app_id:
        return Response({'error': "The 'app_id' query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

    review_qs = get_reviews_for_app_id(app_id).filter(counts_toward_score=False).order_by('-created_at')

    mentions = [
        {
            'content': review.content,
            'sentiment_score': review.sentiment_score,
            'source': review.source,
            'created_at': review.created_at,
            'title': review.title,
            'url': review.review_id,
        }
        for review in review_qs
    ]

    return Response({
        'market_mentions': mentions,
        'total_count': len(mentions),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def competitor_analysis(request):
    """
    Optimized competitor analysis with caching and background task management
    """
    project_id = request.GET.get('project_id')

    if not project_id:
        return Response({
            'error': 'project_id parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get the project and verify ownership
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found or you do not have permission to view it'
        }, status=status.HTTP_404_NOT_FOUND)

    # Create cache key for this project's analysis
    cache_key_data = {
        'endpoint': 'competitor_analysis',
        'project_id': project_id,
        'user_id': request.user.id,
        'timestamp': cache.get(f'last_project_update_{project_id}', 0)
    }
    cache_key = hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()

    # Try to get from cache first
    cached_result = cache.get(f"competitor_analysis_{cache_key}")
    if cached_result:
        # Still check for background tasks even with cached data
        refresh_tasks = check_background_tasks(project, request.user)
        cached_result['refresh_info']['background_refreshes'] = refresh_tasks
        cached_result['cached'] = True
        return Response(cached_result)

    # If not cached, compute results
    profile = UserProfile.objects.get_or_create(user=request.user)[0]

    # Get all app IDs for this project (home app + competitors)
    app_ids = [project.home_app_id]
    competitors = CompetitorApp.objects.filter(project=project)
    app_ids.extend([comp.app_id for comp in competitors])

    # Check for background tasks and trigger refreshes
    refresh_tasks = check_and_trigger_refreshes(project, request.user, profile, competitors, app_ids)

    # Get reviews grouped by app using optimized database queries
    apps_data = {}

    for app_id in app_ids:
        # Use database aggregation instead of Python loops for better performance
        stats = Review.objects.filter(
            app_id=app_id,
            sentiment_score__isnull=False
        ).aggregate(
            total=Count('id'),
            positive=Count('id', filter=Q(sentiment_score__gt=0.1)),
            negative=Count('id', filter=Q(sentiment_score__lt=-0.1)),
            avg_sentiment=Avg('sentiment_score')
        )

        total = stats['total'] or 0
        positive = stats['positive'] or 0
        negative = stats['negative'] or 0
        neutral = total - positive - negative

        # Determine app name and type
        if app_id == project.home_app_id:
            app_name = project.home_app_name
            app_type = "home"
        else:
            competitor = competitors.filter(app_id=app_id).first()
            app_name = competitor.app_name if competitor else app_id
            app_type = "competitor"

        apps_data[app_id] = {
            'app_name': app_name,
            'app_type': app_type,
            'total_reviews': total,
            'positive_count': positive,
            'negative_count': negative,
            'neutral_count': neutral,
            'positive_percentage': round((positive / total * 100), 1) if total > 0 else 0,
            'negative_percentage': round((negative / total * 100), 1) if total > 0 else 0,
            'neutral_percentage': round((neutral / total * 100), 1) if total > 0 else 0,
            'avg_sentiment': round(stats['avg_sentiment'] or 0, 3)
        }

    # Calculate market insights
    total_reviews_analyzed = sum(data['total_reviews'] for data in apps_data.values())
    apps_with_data = len([data for data in apps_data.values() if data['total_reviews'] > 0])

    result = {
        'project_info': {
            'project_id': project.id,
            'project_name': project.name,
            'home_app': project.home_app_name,
            'competitors_count': len(competitors)
        },
        'competitor_analysis': apps_data,
        'market_insight': f"Analyzed {apps_with_data} apps from your project with {total_reviews_analyzed} total reviews",
        'apps_analyzed': len(app_ids),
        'refresh_info': {
            'background_refreshes': refresh_tasks,
            'message': f"Data automatically refreshed for {len(refresh_tasks)} apps with stale data (>24h old)" if refresh_tasks else "All data is fresh (less than 24 hours old)"
        },
        'cached': False
    }

    # Cache for 30 minutes (shorter than insights since this includes real-time task info)
    cache.set(f"competitor_analysis_{cache_key}", result, 1800)

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def strategic_performance(request):
    """
    Calculate strategic performance scores with caching for specific app in project context
    """
    project_id = request.GET.get('project_id')
    app_id = request.GET.get('app_id')

    if not project_id or not app_id:
        return Response({'error': 'Both project_id and app_id parameters are required'}, status=400)

    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found or access denied'}, status=404)

    # Create cache key
    cache_key = f"strategic_performance_{project_id}_{app_id}_{cache.get(f'last_data_update_{app_id}', 0)}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return Response(cached_result)

    # Get app's sentiment stats
    target_app_ids = expand_app_ids(app_id)
    app_reviews = Review.objects.filter(app_id__in=target_app_ids, sentiment_score__isnull=False, counts_toward_score=True)
    if not app_reviews.exists():
        return Response({'error': 'No reviews found for this app'}, status=404)

    app_stats = app_reviews.aggregate(
        total=Count('id'),
        avg_sentiment=Avg('sentiment_score'),
        positive=Count('id', filter=Q(sentiment_score__gt=0.1)),
        negative=Count('id', filter=Q(sentiment_score__lt=-0.1))
    )

    # Get competitor apps for comparison
    competitors = list(CompetitorApp.objects.filter(project=project))
    competitor_app_ids = []
    for comp in competitors:
        competitor_app_ids.extend(expand_many_app_ids([comp.app_id, comp.apple_app_id]))

    if project.home_app_id != app_id:
        competitor_app_ids.extend(expand_app_ids(project.home_app_id))

    competitor_app_ids = [identifier for identifier in competitor_app_ids if identifier]

    if competitor_app_ids:
        market_stats = Review.objects.filter(
            app_id__in=competitor_app_ids,
            sentiment_score__isnull=False,
            counts_toward_score=True
        ).aggregate(
            avg_sentiment=Avg('sentiment_score'),
            total=Count('id')
        )
    else:
        market_stats = {'avg_sentiment': 0, 'total': 0}

    # Calculate scores
    app_sentiment = app_stats['avg_sentiment'] or 0
    market_sentiment = market_stats['avg_sentiment'] or 0

    # Churn Risk Score (0-100, lower is better)
    negative_ratio = (app_stats['negative'] or 0) / (app_stats['total'] or 1)
    churn_risk = min(100, int(negative_ratio * 200))

    # Competitive Gap Score (0-100, lower is better)
    sentiment_gap = max(0, market_sentiment - app_sentiment)
    competitive_gap = min(100, int(sentiment_gap * 100))

    # Calculate ranking based on sentiment vs competitors
    if competitor_app_ids:
        better_performers = Review.objects.filter(
            app_id__in=competitor_app_ids,
            sentiment_score__isnull=False,
            counts_toward_score=True
        ).values('app_id').annotate(
            avg_sent=Avg('sentiment_score')
        ).filter(avg_sent__gt=app_sentiment).count()

        ranking = better_performers + 1
    else:
        ranking = 1

    result = {
        'churn_risk_score': churn_risk,
        'competitive_gap_score': competitive_gap,
        'category_ranking': ranking,
        'app_sentiment': round(app_sentiment, 3),
        'market_sentiment': round(market_sentiment, 3),
        'competitors_analyzed': len(competitor_app_ids),
        'cached': False
    }

    cache.set(cache_key, result, 1800)  # Cache for 30 minutes
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_insights_generation(request):
    """
    Trigger background insights generation for an app
    """
    app_id = request.data.get('app_id')
    project_id = request.data.get('project_id')

    if not app_id:
        return Response({'error': 'app_id required'}, status=400)

    # Verify project access if provided
    if project_id:
        try:
            Project.objects.get(id=project_id, user=request.user)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found or access denied'}, status=404)

    # Check if task is already running
    task_key = f"insights_task_{app_id}"
    if cache.get(task_key):
        return Response({
            'message': 'Insights generation already in progress',
            'task_id': cache.get(task_key),
            'status': 'running'
        })

    # Get user profile for subscription tier
    profile = UserProfile.objects.get_or_create(user=request.user)[0]

    # Start background task
    task = import_google_play_reviews_for_user(
        app_id=app_id,
        user_id=request.user.id,
        subscription_tier=profile.subscription_tier
    )

    cache.set(task_key, task.id, 600)  # Track for 10 minutes

    return Response({
        'message': 'Insights generation started',
        'task_id': task.id,
        'status': 'started'
    })


@permission_classes([IsAuthenticated])
@api_view(['GET'])
def task_status(request, task_id):
    """
    Check the status of a background task
    """
    result = AsyncResult(task_id)

    return Response({
        'task_id': task_id,
        'status': result.status,
        'result': result.result if result.ready() else None,
        'progress': getattr(result, 'info', {}) if hasattr(result, 'info') else {}
    })


# Helper functions for background task management
def check_background_tasks(project, user):
    """Check for currently running background tasks"""
    refresh_tasks = []

    try:
        from deepfocal_backend.celery import app as celery_app
        active_tasks = celery_app.control.inspect().active()

        if active_tasks:
            app_ids = [project.home_app_id]
            competitors = CompetitorApp.objects.filter(project=project)
            app_ids.extend([comp.app_id for comp in competitors])

            for worker, tasks in active_tasks.items():
                for task_data in tasks:
                    if task_data['name'] == 'reviews.tasks.collect_reviews_task':
                        task_args = task_data.get('args', [])
                        if task_args and len(task_args) > 0:
                            task_app_id = task_args[0]

                            if task_app_id in app_ids:
                                if task_app_id == project.home_app_id:
                                    app_name = project.home_app_name
                                else:
                                    competitor = competitors.filter(app_id=task_app_id).first()
                                    app_name = competitor.app_name if competitor else task_app_id

                                task_result = AsyncResult(task_data['id'])
                                task_info = {
                                    'app_id': task_app_id,
                                    'app_name': app_name,
                                    'task_id': task_data['id'],
                                    'status': task_result.status
                                }

                                if task_result.status == 'PROGRESS' and task_result.info:
                                    task_info.update({
                                        'current_reviews': task_result.info.get('current_reviews', 0),
                                        'total_reviews': task_result.info.get('total_reviews', 1000),
                                        'progress_percent': task_result.info.get('progress_percent', 0)
                                    })

                                refresh_tasks.append(task_info)
    except Exception as e:
        print(f"Failed to check active tasks: {e}")

    return refresh_tasks


def check_and_trigger_refreshes(project, user, profile, competitors, app_ids):
    """Check for stale data and trigger refreshes as needed"""
    refresh_tasks = check_background_tasks(project, user)

    # Check and trigger refresh for stale data
    for app_id in app_ids:
        # Skip if we already have an active task for this app
        if any(task['app_id'] == app_id for task in refresh_tasks):
            continue

        if project.needs_refresh(app_id):
            try:
                task = import_google_play_reviews_for_user(
                    app_id=app_id,
                    user_id=user.id,
                    subscription_tier=profile.subscription_tier
                )

                if app_id == project.home_app_id:
                    app_name = project.home_app_name
                else:
                    competitor = competitors.filter(app_id=app_id).first()
                    app_name = competitor.app_name if competitor else app_id

                task_result = AsyncResult(task.id)
                task_info = {
                    'app_id': app_id,
                    'app_name': app_name,
                    'task_id': task.id,
                    'status': task_result.status
                }

                if task_result.status == 'PROGRESS' and task_result.info:
                    task_info.update({
                        'current_reviews': task_result.info.get('current_reviews', 0),
                        'total_reviews': task_result.info.get('total_reviews', 1000),
                        'progress_percent': task_result.info.get('progress_percent', 0)
                    })

                refresh_tasks.append(task_info)

                # Update refresh timestamps
                if app_id == project.home_app_id:
                    project.home_app_last_refreshed = datetime.now(timezone.utc)
                    project.save()
                else:
                    competitor = competitors.filter(app_id=app_id).first()
                    if competitor:
                        competitor.last_refreshed = datetime.now(timezone.utc)
                        competitor.save()

                # Invalidate cache for this project
                cache.set(f'last_project_update_{project.id}', int(datetime.now().timestamp()))

            except Exception as e:
                print(f"Failed to trigger refresh for {app_id}: {e}")
                import traceback
                traceback.print_exc()

    return refresh_tasks


# Signal to invalidate cache when new data arrives
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Review)
def invalidate_cache_on_new_review(sender, instance, **kwargs):
    """Invalidate relevant caches when new reviews are added"""
    import time
    timestamp = int(time.time())

    # Update general timestamp
    cache.set('last_data_update', timestamp)

    # Update app-specific timestamp
    if instance.app_id:
        cache.set(f'last_data_update_{instance.app_id}', timestamp)

    # Update project timestamps for projects that include this app
    if instance.app_id:
        projects = Project.objects.filter(
            Q(home_app_id=instance.app_id) |
            Q(competitors__app_id=instance.app_id)
        ).distinct()

        for project in projects:
            cache.set(f'last_project_update_{project.id}', timestamp)

    # Clear cache patterns (if your cache backend supports it)
    try:
        cache.delete_pattern("competitor_analysis_*")
        cache.delete_pattern("enhanced_insights_*")
        cache.delete_pattern("strategic_performance_*")
    except AttributeError:
        # Fallback for cache backends that don't support delete_pattern
        pass
