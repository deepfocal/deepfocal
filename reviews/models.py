from django.db import models
from django.contrib.auth.models import User

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



# Add these new models:

class UserProfile(models.Model):
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='free')
    projects_created = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_project_limit(self):
        limits = {
            'free': 1,
            'starter': 1,
            'pro': 5,
            'enterprise': 999
        }
        return limits.get(self.subscription_tier, 1)


    def get_review_collection_limit(self):
        """Get the maximum reviews that can be collected per app for this subscription tier"""
        limits = {
            'free': 500,        # Free tier: 500 reviews max per app
            'starter': 1000,    # Starter tier: 1000 reviews max per app (paid)
            'pro': 1000,        # Pro tier: 1000 reviews max per app (paid)
            'enterprise': 1000  # Enterprise: 1000 reviews max per app (paid)
        }
        return limits.get(self.subscription_tier, 500)


class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    home_app_id = models.CharField(max_length=255)
    home_app_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    home_app_last_refreshed = models.DateTimeField(null=True, blank=True,
                                                   help_text="When reviews were last fetched for the home app")

    def __str__(self):
        return f"{self.name} - {self.user.username}"

    def needs_refresh(self, app_id=None):
        """Check if app data needs refresh (older than 24 hours)"""
        from datetime import datetime, timezone, timedelta

        if app_id == self.home_app_id:
            last_refreshed = self.home_app_last_refreshed
        else:
            # Check competitor apps
            competitor = self.competitors.filter(app_id=app_id).first()
            last_refreshed = competitor.last_refreshed if competitor else None

        if not last_refreshed:
            return True  # Never refreshed, needs refresh

        # Refresh if data is older than 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        return last_refreshed < cutoff


class CompetitorApp(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='competitors')
    app_id = models.CharField(max_length=255)
    app_name = models.CharField(max_length=200)
    added_at = models.DateTimeField(auto_now_add=True)
    last_refreshed = models.DateTimeField(null=True, blank=True,
                                         help_text="When reviews were last fetched for this competitor app")

    def __str__(self):
        return f"{self.app_name} (competitor of {self.project.name})"


class TaskTracker(models.Model):
    """Track all analysis tasks for reliable progressive disclosure"""
    TASK_TYPES = [
        ('quick', 'Quick Analysis'),
        ('full', 'Full Analysis'),
        ('refresh', 'Data Refresh'),
    ]

    TASK_STATUS = [
        ('pending', 'Pending'),
        ('started', 'Started'),
        ('progress', 'In Progress'),
        ('success', 'Completed'),
        ('failure', 'Failed'),
        ('revoked', 'Cancelled'),
    ]

    # Task identification
    task_id = models.CharField(max_length=255, unique=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)

    # App and user info
    app_id = models.CharField(max_length=255)
    app_name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)

    # Task status and progress
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='pending')
    current_reviews = models.IntegerField(default=0)
    target_reviews = models.IntegerField(default=200)
    progress_percent = models.FloatField(default=0.0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Result info
    result_message = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    def is_active(self):
        """Check if task is currently running"""
        return self.status in ['pending', 'started', 'progress']

    def is_complete(self):
        """Check if task finished (success or failure)"""
        return self.status in ['success', 'failure', 'revoked']

    def update_progress(self, current_reviews, target_reviews=None, status='progress'):
        """Update task progress"""
        self.current_reviews = current_reviews
        if target_reviews:
            self.target_reviews = target_reviews
        self.progress_percent = min(100.0, (current_reviews / self.target_reviews) * 100)
        self.status = status

        if status == 'started' and not self.started_at:
            from django.utils import timezone
            self.started_at = timezone.now()
        elif status in ['success', 'failure', 'revoked'] and not self.completed_at:
            from django.utils import timezone
            self.completed_at = timezone.now()

        self.save()

    def __str__(self):
        return f"{self.task_type} - {self.app_name} ({self.status})"

    class Meta:
        ordering = ['-created_at']

