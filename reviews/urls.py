# file: reviews/urls.py
from django.urls import path
from .views import ReviewListView, insights_summary
from django.urls import path
from .views import ReviewListView, insights_summary, competitor_analysis

urlpatterns = [
    path('reviews/', ReviewListView.as_view(), name='review-list'),
    path('insights/', insights_summary, name='insights-summary'),
    path('competitor-analysis/', competitor_analysis, name='competitor-analysis'),
]
