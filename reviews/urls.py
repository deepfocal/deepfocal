# file: reviews/urls.py
from django.urls import path
from .views import ReviewListView, enhanced_insights_summary, competitor_analysis

urlpatterns = [
    path('reviews/', ReviewListView.as_view(), name='review-list'),
    path('enhanced-insights/', enhanced_insights_summary, name='enhanced-insights'),
    path('competitor-analysis/', competitor_analysis, name='competitor-analysis'),
]