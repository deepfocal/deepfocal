from django.db import models


class Review(models.Model):
    """
    Represents a single customer review scraped from a public source.
    """
    review_id = models.CharField(max_length=255, unique=True)
    source = models.CharField(max_length=100)  # e.g., 'Apple App Store', 'Google Play Store'
    author = models.CharField(max_length=255, null=True, blank=True)
    rating = models.IntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField()

    sentiment_label = models.CharField(max_length=20, null=True, blank=True)  # e.g., 'POSITIVE', 'NEGATIVE'
    sentiment_score = models.FloatField(null=True, blank=True)  # e.g., 0.9987

    created_at = models.DateTimeField(auto_now_add=True)
    # ... (__str__ method is here)

    def __str__(self):
        return f"{self.source} - {self.title}"