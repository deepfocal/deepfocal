# file: reviews/views.py
from rest_framework import generics
from .models import Review
from .serializers import ReviewSerializer

class ReviewListView(generics.ListAPIView):
    queryset = Review.objects.all().order_by('-created_at') # Get all reviews, newest first
    serializer_class = ReviewSerializer