# New task-centric API for reliable progressive disclosure
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import TaskTracker, Project, CompetitorApp, UserProfile, Review
from .tasks import import_google_play_reviews_for_user
from django.db.models import Q


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_analysis_status(request, project_id):
    """
    Get current analysis status for a project using TaskTracker.
    This replaces the complex competitor_analysis endpoint.
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Get user profile for limits and all app IDs for this project
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    review_limit = profile.get_review_collection_limit()

    # Get all app IDs for this project
    app_ids = [project.home_app_id]
    competitors = CompetitorApp.objects.filter(project=project)
    app_ids.extend([comp.app_id for comp in competitors])

    # Get current tasks for these apps
    active_tasks = TaskTracker.objects.filter(
        app_id__in=app_ids,
        user=request.user,
        status__in=['pending', 'started', 'progress']
    ).order_by('-created_at')

    # Get review data for each app
    apps_data = {}
    task_data = []

    for app_id in app_ids:
        # Get app info
        if app_id == project.home_app_id:
            app_name = project.home_app_name
            app_type = "home"
        else:
            competitor = competitors.filter(app_id=app_id).first()
            app_name = competitor.app_name if competitor else app_id
            app_type = "competitor"

        # Get review stats
        app_reviews = Review.objects.filter(app_id=app_id, sentiment_score__isnull=False)
        total = app_reviews.count()
        positive = app_reviews.filter(sentiment_score__gt=0.1).count()
        negative = app_reviews.filter(sentiment_score__lt=-0.1).count()
        neutral = total - positive - negative

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
            'review_limit': review_limit,
            'remaining_reviews': max(review_limit - total, 0),
            'can_collect_more': total < review_limit,
        }

        # Check for active tasks for this app
        app_task = active_tasks.filter(app_id=app_id).first()
        if app_task:
            task_data.append({
                'task_id': app_task.task_id,
                'app_id': app_id,
                'app_name': app_name,
                'task_type': app_task.task_type,
                'status': app_task.status,
                'current_reviews': app_task.current_reviews,
                'target_reviews': app_task.target_reviews,
                'progress_percent': app_task.progress_percent,
                'created_at': app_task.created_at,
            })

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
        'message': f"Found {len(task_data)} active tasks" if task_data else "No active tasks",
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
            'task_status': existing_task.status
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
