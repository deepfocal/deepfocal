from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from .models import Project, CompetitorApp, UserProfile, Review, TaskTracker
from .tasks import import_google_play_reviews_for_user, import_google_play_reviews_full_analysis
from celery.result import AsyncResult


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_project(request):
    """
    Create a new project for the authenticated user
    """
    name = request.data.get('name')
    home_app_id = request.data.get('home_app_id')
    home_app_name = request.data.get('home_app_name')

    if not all([name, home_app_id, home_app_name]):
        return Response({
            'error': 'Name, home_app_id, and home_app_name are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get user profile and check project limits
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    user_projects_count = Project.objects.filter(user=request.user).count()

    if user_projects_count >= profile.get_project_limit():
        return Response({
            'error': f'Project limit reached. Your {profile.subscription_tier} plan allows {profile.get_project_limit()} project(s)'
        }, status=status.HTTP_403_FORBIDDEN)

    # Check if project name already exists for this user
    if Project.objects.filter(user=request.user, name=name).exists():
        return Response({
            'error': 'Project with this name already exists'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Create the project
    project = Project.objects.create(
        user=request.user,
        name=name,
        home_app_id=home_app_id,
        home_app_name=home_app_name
    )

    # Update user profile projects count
    profile.projects_created += 1
    profile.save()

    # Automatically trigger review import for the home app with subscription limits
    try:
        task_result = import_google_play_reviews_for_user(
            app_id=home_app_id,
            user_id=request.user.id,
            subscription_tier=profile.subscription_tier,
            app_name=home_app_name,
            project_id=project.id
        )
        task_id = task_result.id
        import_status = "started"
    except Exception as e:
        # Don't fail project creation if review import fails
        task_id = None
        import_status = "failed"
        print(f"Failed to start review import for home app {home_app_id}: {e}")

    return Response({
        'id': project.id,
        'name': project.name,
        'home_app_id': project.home_app_id,
        'home_app_name': project.home_app_name,
        'created_at': project.created_at,
        'competitors_count': 0,
        'home_app_import': {
            'status': import_status,
            'task_id': task_id,
            'message': f'Review import {import_status} for {home_app_name}'
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_projects(request):
    """
    List all projects for the authenticated user
    """
    projects = Project.objects.filter(user=request.user).order_by('-created_at')

    projects_data = []
    for project in projects:
        competitors_count = project.competitors.count()
        projects_data.append({
            'id': project.id,
            'name': project.name,
            'home_app_id': project.home_app_id,
            'home_app_name': project.home_app_name,
            'created_at': project.created_at,
            'competitors_count': competitors_count
        })

    # Also include user limits for frontend
    profile = UserProfile.objects.get_or_create(user=request.user)[0]

    return Response({
        'projects': projects_data,
        'user_limits': {
            'project_limit': profile.get_project_limit(),
            'review_collection_limit': profile.get_review_collection_limit(),
            'subscription_tier': profile.subscription_tier,
            'unlimited_dashboard_access': True,
            'competitor_limit': profile.get_competitor_limit(),
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_competitor(request):
    """
    Add a competitor app to an existing project
    """
    project_id = request.data.get('project_id')
    app_id = request.data.get('app_id')
    app_name = request.data.get('app_name')

    if not all([project_id, app_id, app_name]):
        return Response({
            'error': 'project_id, app_id, and app_name are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get the project and verify ownership
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found or you do not have permission to modify it'
        }, status=status.HTTP_404_NOT_FOUND)

    # Note: No longer limiting competitor count, usage-based limits apply to analysis requests

    # Check if competitor already exists in this project
    if CompetitorApp.objects.filter(project=project, app_id=app_id).exists():
        return Response({
            'error': 'This app is already a competitor in this project'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Create the competitor
    competitor = CompetitorApp.objects.create(
        project=project,
        app_id=app_id,
        app_name=app_name
    )

    # Automatically trigger review import for the new competitor with subscription limits
    try:
        # Get user profile for subscription tier
        profile = UserProfile.objects.get_or_create(user=request.user)[0]
        task_result = import_google_play_reviews_for_user(
            app_id=app_id,
            user_id=request.user.id,
            subscription_tier=profile.subscription_tier,
            app_name=app_name,
            project_id=project.id
        )
        task_id = task_result.id
        import_status = "started"
    except Exception as e:
        # Don't fail competitor creation if review import fails
        task_id = None
        import_status = "failed"
        print(f"Failed to start review import for {app_id}: {e}")

    return Response({
        'id': competitor.id,
        'app_id': competitor.app_id,
        'app_name': competitor.app_name,
        'project_id': project.id,
        'added_at': competitor.added_at,
        'review_import': {
            'status': import_status,
            'task_id': task_id,
            'message': f'Review import {import_status} for {app_name}'
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_details(request, project_id):
    """
    Get detailed information about a specific project including competitors
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found or you do not have permission to view it'
        }, status=status.HTTP_404_NOT_FOUND)

    competitors = CompetitorApp.objects.filter(project=project).order_by('-added_at')
    competitors_data = [{
        'id': comp.id,
        'app_id': comp.app_id,
        'app_name': comp.app_name,
        'added_at': comp.added_at
    } for comp in competitors]

    return Response({
        'id': project.id,
        'name': project.name,
        'home_app_id': project.home_app_id,
        'home_app_name': project.home_app_name,
        'created_at': project.created_at,
        'competitors': competitors_data
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_project(request, project_id):
    """
    Delete a project and cascade associated competitor data for the authenticated user.
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found or you do not have permission to delete it'
        }, status=status.HTTP_404_NOT_FOUND)

    app_ids = [project.home_app_id]
    app_ids.extend(project.competitors.values_list('app_id', flat=True))
    app_ids = [app_id for app_id in app_ids if app_id]

    with transaction.atomic():
        if app_ids:
            Review.objects.filter(app_id__in=app_ids).delete()
        TaskTracker.objects.filter(project=project).delete()
        project.delete()

    remaining_projects = Project.objects.filter(user=request.user).count()

    return Response({
        'message': 'Project deleted successfully',
        'deleted_project_id': project_id,
        'remaining_projects': remaining_projects,
        'removed_app_ids': app_ids,
    }, status=status.HTTP_200_OK)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_competitor(request, competitor_id):
    """
    Remove a competitor from a project
    """
    try:
        competitor = CompetitorApp.objects.get(
            id=competitor_id,
            project__user=request.user
        )
        competitor.delete()
        return Response({
            'message': 'Competitor removed successfully'
        }, status=status.HTTP_200_OK)
    except CompetitorApp.DoesNotExist:
        return Response({
            'error': 'Competitor not found or you do not have permission to delete it'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_status(request, task_id):
    """
    Check the status of a background task (like review import)
    """
    try:
        result = AsyncResult(task_id)

        response_data = {
            'task_id': task_id,
            'status': result.status,
            'ready': result.ready()
        }

        if result.ready():
            if result.successful():
                response_data['result'] = result.result
            else:
                response_data['error'] = str(result.result)
        else:
            response_data['info'] = result.info

        return Response(response_data)

    except Exception as e:
        return Response({
            'error': f'Failed to get task status: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_to_full_analysis(request):
    """
    Upgrade a competitor from quick analysis (200 reviews) to full analysis.
    This collects the remaining reviews for deeper insights.
    """
    app_id = request.data.get('app_id')

    if not app_id:
        return Response({
            'error': 'app_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verify the user has access to this app through their projects
    user_projects = Project.objects.filter(user=request.user)
    has_access = False

    for project in user_projects:
        if project.home_app_id == app_id:
            has_access = True
            app_name = project.home_app_name
            break
        competitor = CompetitorApp.objects.filter(project=project, app_id=app_id).first()
        if competitor:
            has_access = True
            app_name = competitor.app_name
            break

    if not has_access:
        return Response({
            'error': 'You do not have access to this app'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        # Get user profile for subscription tier
        profile = UserProfile.objects.get_or_create(user=request.user)[0]

        # Trigger full analysis task
        task_result = import_google_play_reviews_full_analysis(
            app_id=app_id,
            user_id=request.user.id,
            subscription_tier=profile.subscription_tier
        )

        return Response({
            'message': f'Full analysis started for {app_name}',
            'task_id': task_result.id,
            'app_id': app_id,
            'app_name': app_name,
            'analysis_type': 'full'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': f'Failed to start full analysis: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
