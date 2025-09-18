# file: reviews/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from .models import Review, Project, CompetitorApp, UserProfile
from .serializers import ReviewSerializer
from .topic_modeling import analyze_app_topics
from .tasks import import_google_play_reviews_for_user
from celery.result import AsyncResult
from datetime import datetime, timezone

class ReviewListView(generics.ListAPIView):
    queryset = Review.objects.all().order_by('-created_at') # Get all reviews, newest first
    serializer_class = ReviewSerializer


@api_view(['GET'])
def enhanced_insights_summary(request):
    """
    Enhanced insights using LDA topic modeling instead of keyword matching
    """
    # --- THIS IS THE FIX ---
    # Get the app_id from the URL's query parameters
    app_id = request.GET.get('app_id', None)

    # Check if the app_id was provided. If not, return a clear error.
    if not app_id:
        return Response(
            {"error": "The 'app_id' query parameter is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    # --- END OF THE FIX ---

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
    review_count = lda_results.get('review_count', 0)
    raw_review_count = lda_results.get('raw_review_count', review_count)
    filtered_out = lda_results.get('filtered_out_reviews', max(raw_review_count - review_count, 0))

    return Response({
        'lda_pain_points': pain_points,
        'review_count_analyzed': review_count,
        'raw_review_count': raw_review_count,
        'filtered_out_reviews': filtered_out,
        'app_id': app_id
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def competitor_analysis(request):
    """
    Compare sentiment and pain points across apps in a specific user project.
    This is the 'voice of the market' feature that differentiates Deepfocal.
    """
    from collections import defaultdict
    from .tasks import extract_pain_points

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

    # Check if any apps need refresh and trigger background updates

    profile = UserProfile.objects.get_or_create(user=request.user)[0]

    # Get all app IDs for this project (home app + competitors)
    app_ids = [project.home_app_id]
    competitors = CompetitorApp.objects.filter(project=project)
    app_ids.extend([comp.app_id for comp in competitors])

    # Check for currently running tasks AND trigger refresh for stale data
    refresh_tasks = []

    # Check for currently running tasks
    try:
        from deepfocal_backend.celery import app as celery_app
        active_tasks = celery_app.control.inspect().active()

        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task_data in tasks:
                    if task_data['name'] == 'reviews.tasks.collect_reviews_task':
                        # Extract app_id from task args
                        task_args = task_data.get('args', [])
                        if task_args and len(task_args) > 0:
                            task_app_id = task_args[0]  # First argument is app_id

                            # Check if this task is for one of our apps
                            if task_app_id in app_ids:
                                # Get app name
                                if task_app_id == project.home_app_id:
                                    app_name = project.home_app_name
                                else:
                                    competitor = competitors.filter(app_id=task_app_id).first()
                                    app_name = competitor.app_name if competitor else task_app_id

                                # Get detailed task status
                                task_result = AsyncResult(task_data['id'])

                                task_info = {
                                    'app_id': task_app_id,
                                    'app_name': app_name,
                                    'task_id': task_data['id'],
                                    'status': task_result.status
                                }

                                # Add progress info if available
                                if task_result.status == 'PROGRESS' and task_result.info:
                                    task_info.update({
                                        'current_reviews': task_result.info.get('current_reviews', 0),
                                        'total_reviews': task_result.info.get('total_reviews', 1000),
                                        'progress_percent': task_result.info.get('progress_percent', 0)
                                    })

                                refresh_tasks.append(task_info)
    except Exception as e:
        print(f"Failed to check active tasks: {e}")

    # Then, check and trigger refresh for stale data (older than 24 hours)
    for app_id in app_ids:
        # Skip if we already have an active task for this app
        if any(task['app_id'] == app_id for task in refresh_tasks):
            continue

        if project.needs_refresh(app_id):
            try:
                # Trigger background refresh for stale data
                task = import_google_play_reviews_for_user(
                    app_id=app_id,
                    user_id=request.user.id,
                    subscription_tier=profile.subscription_tier
                )

                # Get app name for the task info
                if app_id == project.home_app_id:
                    app_name = project.home_app_name
                else:
                    competitor = competitors.filter(app_id=app_id).first()
                    app_name = competitor.app_name if competitor else app_id

                # Check task status and get progress info
                task_result = AsyncResult(task.id)

                task_info = {
                    'app_id': app_id,
                    'app_name': app_name,
                    'task_id': task.id,
                    'status': task_result.status
                }

                # Add progress info if available
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

            except Exception as e:
                # Don't fail the analysis if refresh fails
                print(f"Failed to trigger refresh for {app_id}: {e}")
                # Log the actual error for debugging
                import traceback
                traceback.print_exc()

    # Get reviews grouped by app
    apps_data = {}

    for app_id in app_ids:
        app_reviews = Review.objects.filter(app_id=app_id, sentiment_score__isnull=False)
        total = app_reviews.count()
        positive = app_reviews.filter(sentiment_score__gt=0.1).count()
        negative = app_reviews.filter(sentiment_score__lt=-0.1).count()
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
        }

    # Calculate market insights
    total_reviews_analyzed = sum(data['total_reviews'] for data in apps_data.values())
    apps_with_data = len([data for data in apps_data.values() if data['total_reviews'] > 0])

    return Response({
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
        }
    })
