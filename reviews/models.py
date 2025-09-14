from django.db import models

class Review(models.Model):
    """
    Represents a single customer review scraped from a public source.
    """
    app_id = models.CharField(max_length=255, null=True, blank=True,
                              help_text="The app store ID this review belongs to")
    review_id = models.CharField(max_length=255, unique=True)
    source = models.CharField(max_length=100)  # e.g., 'Apple App Store', 'Google Play Store'
    author = models.CharField(max_length=255, null=True, blank=True)
    rating = models.IntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField()
    sentiment_score = models.FloatField(null=True, blank=True,
                                      help_text="Sentiment score from -1 (negative) to 1 (positive)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} - {self.title}"