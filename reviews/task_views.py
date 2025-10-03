# New task-centric API for reliable progressive disclosure
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import TaskTracker, Project, CompetitorApp, UserProfile, Review
from .app_id_utils import expand_many_app_ids
from .tasks import import_google_play_reviews_for_user
from django.db.models import Q, Count, Avg


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_analysis_status(request, project_id):
    """Get current analysis status for a project using TaskTracker."""
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    review_limit = profile.get_review_collection_limit()

    competitors = list(CompetitorApp.objects.filter(project=project))

    entries = []
    home_app_ids = expand_many_app_ids([project.home_app_id, project.apple_app_id])
    entries.append({
        'key': project.home_app_id,
        'name': project.home_app_name,
        'type': 'home',
        'app_ids': home_app_ids,
        'competitor': None,
    })

    for competitor in competitors:
        competitor_ids = expand_many_app_ids([competitor.app_id, competitor.apple_app_id])
        entries.append({
            'key': competitor.app_id,
            'name': competitor.app_name,
            'type': 'competitor',
            'app_ids': competitor_ids,
            'competitor': competitor,
        })

    task_app_ids = {identifier for entry in entries for identifier in entry['app_ids']}

    active_tasks = list(TaskTracker.objects.filter(
        app_id__in=task_app_ids,
        user=request.user,
        status__in=['pending', 'started', 'progress'],
    ).order_by('-created_at'))

    latest_task_by_app = {}
    for task in active_tasks:
        latest_task_by_app.setdefault(task.app_id, task)

    apps_data = {}
    task_data = []

    for entry in entries:
        app_ids = entry['app_ids']
        stats = Review.objects.filter(
            app_id__in=app_ids,
            sentiment_score__isnull=False,
            counts_toward_score=True,
        ).aggregate(
            total=Count('id'),
            positive=Count('id', filter=Q(sentiment_score__gt=0.1)),
            negative=Count('id', filter=Q(sentiment_score__lt=-0.1)),
            avg_sentiment=Avg('sentiment_score'),
        )

        total = stats['total'] or 0
        positive = stats['positive'] or 0
        negative = stats['negative'] or 0
        neutral = max(total - positive - negative, 0)

        competitor_obj = entry['competitor']
        app_payload = {
            'app_name': entry['name'],
            'app_type': entry['type'],
            'competitor_id': competitor_obj.id if competitor_obj else None,
            'added_at': competitor_obj.added_at.isoformat() if competitor_obj else None,
            'total_reviews': total,
            'positive_count': positive,
            'negative_count': negative,
            'neutral_count': neutral,
            'positive_percentage': round((positive / total * 100), 1) if total > 0 else 0,
            'negative_percentage': round((negative / total * 100), 1) if total > 0 else 0,
            'neutral_percentage': round((neutral / total * 100), 1) if total > 0 else 0,
            'review_limit': review_limit,
            'remaining_reviews': max(review_limit - total, 0),
            'can_collect_more': total < review_limit,
            'combined_app_ids': app_ids,
        }

        task_candidates = [latest_task_by_app[identifier] for identifier in app_ids if identifier in latest_task_by_app]
        if task_candidates:
            task = max(task_candidates, key=lambda item: item.created_at)
            app_payload['status'] = task.status
            app_payload['review_import'] = {
                'status': task.status,
                'task_id': task.task_id,
                'progress_percent': task.progress_percent,
            }
            task_data.append({
                'task_id': task.task_id,
                'app_id': task.app_id,
                'app_name': entry['name'],
                'task_type': task.task_type,
                'status': task.status,
                'current_reviews': task.current_reviews,
                'target_reviews': task.target_reviews,
                'progress_percent': task.progress_percent,
                'created_at': task.created_at,
            })
        else:
            app_payload['status'] = 'idle' if total > 0 else 'pending'

        apps_data[entry['key']] = app_payload

    return Response({
        'project_info': {
            'project_id': project.id,
            'project_name': project.name,
            'home_app': project.home_app_name,
            'competitors_count': len(competitors)
        },
        'competitor_analysis': apps_data,
        'active_tasks': task_data,
        'has_active_tasks': len(task_data) > 0,
        'message': f"Found {len(task_data)} active tasks" if task_data else 'No active tasks',
        'review_limit': review_limit,
        'subscription_tier': profile.subscription_tier,
    })
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_analysis(request):
    """
    Start analysis for a specific app with proper task tracking.
    """
    app_id = request.data.get('app_id')
    analysis_type = request.data.get('analysis_type', 'quick')  # 'quick' or 'full'
    project_id = request.data.get('project_id')

    if not app_id:
        return Response({
            'error': 'app_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verify user has access to this app
    try:
        project = Project.objects.get(id=project_id, user=request.user)

        if app_id == project.home_app_id:
            app_name = project.home_app_name
        else:
            competitor = CompetitorApp.objects.filter(project=project, app_id=app_id).first()
            if not competitor:
                return Response({
                    'error': 'App not found in this project'
                }, status=status.HTTP_404_NOT_FOUND)
            app_name = competitor.app_name

    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Check if there's already an active task for this app
    existing_task = TaskTracker.objects.filter(
        app_id=app_id,
        user=request.user,
        status__in=['pending', 'started', 'progress']
    ).first()

    if existing_task:
        return Response({
            'error': f'Analysis already in progress for {app_name}',
            'existing_task_id': existing_task.task_id,
            'task_status': existing_task.status,
            'task_type': existing_task.task_type,
        }, status=status.HTTP_409_CONFLICT)

    # Get user profile
    profile = UserProfile.objects.get_or_create(user=request.user)[0]

    # Start the analysis
    try:
        task_result = import_google_play_reviews_for_user(
            app_id=app_id,
            user_id=request.user.id,
            subscription_tier=profile.subscription_tier,
            quick_analysis=(analysis_type == 'quick'),
            app_name=app_name,
            project_id=project.id
        )

        return Response({
            'message': f'{analysis_type.title()} analysis started for {app_name}',
            'task_id': task_result.id,
            'app_id': app_id,
            'app_name': app_name,
            'analysis_type': analysis_type
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'error': f'Failed to start analysis: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_status_detail(request, task_id):
    """
    Get detailed status of a specific task.
    """
    try:
        task = TaskTracker.objects.get(task_id=task_id, user=request.user)
        return Response({
            'task_id': task.task_id,
            'app_id': task.app_id,
            'app_name': task.app_name,
            'task_type': task.task_type,
            'status': task.status,
            'current_reviews': task.current_reviews,
            'target_reviews': task.target_reviews,
            'progress_percent': task.progress_percent,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'result_message': task.result_message,
            'error_message': task.error_message,
        })
    except TaskTracker.DoesNotExist:
        return Response({
            'error': 'Task not found'
        }, status=status.HTTP_404_NOT_FOUND)





