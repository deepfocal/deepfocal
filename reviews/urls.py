# file: reviews/urls.py
from django.urls import path
from .views import ReviewListView, enhanced_insights_summary, competitor_analysis, strategic_performance, trigger_insights_generation
from .views import task_status as views_task_status
from .auth_views import register, login, user_profile, logout
from .demo_views import demo_dashboard
from .project_views import (
    create_project,
    list_projects,
    add_competitor,
    get_project_details,
    delete_project,
    delete_competitor,
    task_status,
    upgrade_to_full_analysis,
)
from .task_views import project_analysis_status, start_analysis, task_status_detail
from .dashboard_views import (
    project_strategic_scores,
    project_sentiment_trends,
    strengths_insights,
)

urlpatterns = [
    path('reviews/', ReviewListView.as_view(), name='review-list'),
    path('enhanced-insights/', enhanced_insights_summary, name='enhanced-insights'),
    path('competitor-analysis/', competitor_analysis, name='competitor-analysis'),
    path('strengths/', strengths_insights, name='strengths-insights'),
    path('strategic-performance/', strategic_performance, name='strategic-performance'),
    path('trigger-insights/', trigger_insights_generation, name='trigger-insights'),
    path('task-status/<str:task_id>/', views_task_status, name='api-task-status'),

    # Authentication endpoints
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/profile/', user_profile, name='user-profile'),
    path('auth/logout/', logout, name='logout'),

    # Project management endpoints
    path('projects/', list_projects, name='list-projects'),
    path('projects/create/', create_project, name='create-project'),
    path('projects/<int:project_id>/', get_project_details, name='project-details'),
    path('projects/add-competitor/', add_competitor, name='add-competitor'),
    path('projects/<int:project_id>/delete/', delete_project, name='delete-project'),
    path('competitors/<int:competitor_id>/delete/', delete_competitor, name='delete-competitor'),

    # Background task monitoring
    path('tasks/<str:task_id>/status/', task_status, name='task-status'),

    # Progressive disclosure analysis
    path('analysis/upgrade-to-full/', upgrade_to_full_analysis, name='upgrade-to-full-analysis'),

    # Demo endpoints
    path('demo/dashboard/', demo_dashboard, name='demo-dashboard'),
    # New dashboard + task-centric API endpoints
    path('projects/<int:project_id>/status/', project_analysis_status, name='project-analysis-status'),
    path('projects/<int:project_id>/strategic-scores/', project_strategic_scores, name='project-strategic-scores'),
    path('projects/<int:project_id>/sentiment-trends/', project_sentiment_trends, name='project-sentiment-trends'),
    path('analysis/start/', start_analysis, name='start-analysis'),
    path('tasks/<str:task_id>/detail/', task_status_detail, name='task-status-detail'),
]
