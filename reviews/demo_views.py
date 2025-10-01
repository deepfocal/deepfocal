from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from datetime import datetime, timedelta


@api_view(['GET'])
@permission_classes([AllowAny])
def demo_dashboard(request):
    base_date = datetime.now() - timedelta(weeks=8)

    # Generate 8 weeks of sentiment data for Momentum (improving trend)
    momentum_series = []
    for week in range(8):
        date = base_date + timedelta(weeks=week)
        momentum_series.append({
            'date': date.strftime('%b %d'),
            'positive': 58 + (week * 2),  # Improves from 58% to 72%
            'negative': 25 - (week * 1),  # Decreases from 25% to 18%
            'competitor': 52  # TaskFlow comparison line
        })

    # Generate 8 weeks of sentiment data for TaskFlow (flat performance)
    taskflow_series = []
    for week in range(8):
        date = base_date + timedelta(weeks=week)
        taskflow_series.append({
            'date': date.strftime('%b %d'),
            'positive': 52,  # Stays flat at 52%
            'negative': 32,  # Stays flat at 32%
            'competitor': None
        })

    # Create demo project
    demo_project = {
        'id': 1,
        'name': 'Demo Project',
        'home_app_id': 'com.momentum.app',
        'home_app_name': 'Momentum',
        'competitors_count': 1,
        'created_at': '2024-01-01T00:00:00Z'
    }

    return Response({
        'projects': [demo_project],
        'user_limits': {
            'project_limit': 3,
            'competitor_limit': 5,
            'subscription_tier': 'demo'
        },
        'status': {
            'competitor_analysis': {
                'com.momentum.app': {
                    'app_id': 'com.momentum.app',
                    'app_name': 'Momentum',
                    'app_type': 'home',
                    'positive_percentage': 72.0,
                    'negative_percentage': 18.0,
                    'neutral_percentage': 10.0,
                    'total_reviews': 1250,
                    'positive_count': 900,
                    'negative_count': 225,
                    'neutral_count': 125
                },
                'com.taskflow.app': {
                    'app_id': 'com.taskflow.app',
                    'app_name': 'TaskFlow',
                    'app_type': 'competitor',
                    'competitor_id': 1,
                    'positive_percentage': 52.0,
                    'negative_percentage': 32.0,
                    'neutral_percentage': 16.0,
                    'total_reviews': 980,
                    'positive_count': 510,
                    'negative_count': 314,
                    'neutral_count': 156
                }
            }
        },
        'sentiment': {
            'series': {
                'com.momentum.app': momentum_series,
                'com.taskflow.app': taskflow_series
            }
        },
        'pain_points': {
            'com.momentum.app': [
                {
                    'id': 'momentum-pain-1',
                    'title': 'Sync Issues',
                    'mentions': 45,
                    'percentage': 20.0,
                    'quotes': [
                        'Tasks not syncing between devices properly',
                        'Lost work due to sync problems',
                        'Sync delay affects team collaboration'
                    ]
                },
                {
                    'id': 'momentum-pain-2',
                    'title': 'Offline Mode',
                    'mentions': 32,
                    'percentage': 14.2,
                    'quotes': [
                        'Offline mode needs improvement',
                        'Changes do not save when offline',
                        'Lost data when working without internet'
                    ]
                },
                {
                    'id': 'momentum-pain-3',
                    'title': 'Performance Issues',
                    'mentions': 28,
                    'percentage': 12.4,
                    'quotes': [
                        'App is slow with large task lists',
                        'Laggy when switching between projects',
                        'Takes too long to load on startup'
                    ]
                }
            ],
            'com.taskflow.app': [
                {
                    'id': 'taskflow-pain-1',
                    'title': 'Confusing Interface',
                    'mentions': 89,
                    'percentage': 28.3,
                    'quotes': [
                        'Too many features make it overwhelming',
                        'Cannot find basic settings',
                        'Navigation is not intuitive'
                    ]
                },
                {
                    'id': 'taskflow-pain-2',
                    'title': 'Poor Mobile Experience',
                    'mentions': 67,
                    'percentage': 21.3,
                    'quotes': [
                        'Mobile app is buggy and crashes often',
                        'Desktop features missing on mobile',
                        'Hard to use on smaller screens'
                    ]
                },
                {
                    'id': 'taskflow-pain-3',
                    'title': 'Expensive Pricing',
                    'mentions': 54,
                    'percentage': 17.2,
                    'quotes': [
                        'Too expensive for what it offers',
                        'Cheaper alternatives available',
                        'Not worth the monthly subscription'
                    ]
                }
            ]
        },
        'strengths': {
            'com.momentum.app': [
                {
                    'id': 'momentum-strength-1',
                    'title': 'Clean Interface',
                    'mentions': 156,
                    'percentage': 17.3,
                    'quotes': [
                        'Love the minimal, distraction-free design',
                        'Interface is intuitive and easy to use',
                        'Beautiful and functional at the same time'
                    ]
                },
                {
                    'id': 'momentum-strength-2',
                    'title': 'Great Features',
                    'mentions': 134,
                    'percentage': 14.9,
                    'quotes': [
                        'Project templates save so much time',
                        'Recurring tasks work perfectly',
                        'Love the quick capture feature'
                    ]
                },
                {
                    'id': 'momentum-strength-3',
                    'title': 'Excellent Support',
                    'mentions': 98,
                    'percentage': 10.9,
                    'quotes': [
                        'Support team responds within hours',
                        'They actually listen to feedback',
                        'Best customer service I have experienced'
                    ]
                }
            ],
            'com.taskflow.app': [
                {
                    'id': 'taskflow-strength-1',
                    'title': 'Powerful Integrations',
                    'mentions': 124,
                    'percentage': 24.3,
                    'quotes': [
                        'Connects with all my tools seamlessly',
                        'API integration works great',
                        'Love the Slack and email integrations'
                    ]
                },
                {
                    'id': 'taskflow-strength-2',
                    'title': 'Advanced Features',
                    'mentions': 98,
                    'percentage': 19.2,
                    'quotes': [
                        'Automation rules are incredibly powerful',
                        'Custom fields let me track everything',
                        'Reporting features are comprehensive'
                    ]
                },
                {
                    'id': 'taskflow-strength-3',
                    'title': 'Team Collaboration',
                    'mentions': 76,
                    'percentage': 14.9,
                    'quotes': [
                        'Great for team projects and coordination',
                        'Comments and mentions work well',
                        'Easy to assign tasks to team members'
                    ]
                }
            ]
        },
        'default_project_id': 1,
        'default_app_id': 'com.momentum.app'
    })