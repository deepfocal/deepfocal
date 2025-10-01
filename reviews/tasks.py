from transformers import pipeline
from celery import shared_task
from google_play_scraper import reviews, Sort
from .models import Review, TaskTracker, Project
import logging
import requests
import xml.etree.ElementTree as ET
from django.contrib.auth.models import User
logger = logging.getLogger(__name__)

# --- Configuration ---
APP_COUNTRY = 'us'
REVIEW_COUNT = 200  # Fetch per request (maximum 200 per request)

# Subscription tier review limits
SUBSCRIPTION_REVIEW_LIMITS = {
    'free': 500,        # Free tier: 500 reviews max per app
    'starter': 1000,    # Starter tier: 1000 reviews max per app (paid)
    'pro': 1000,        # Pro tier: 1000 reviews max per app (paid)
    'enterprise': 1000  # Enterprise: 1000 reviews max per app (paid)
}

# Hard system maximum - never collect more than this regardless of subscription
HARD_SYSTEM_MAX_REVIEWS = 2000

@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=300,
    bind=True
)
def collect_reviews_task(self, app_id, max_reviews, user_id=None, subscription_tier='free', app_name=None, task_type='quick'):
    """
    Enhanced task with persistent tracking using TaskTracker model.
    """
    logger.info(f"Starting review collection for app: {app_id}, max: {max_reviews}, user: {user_id}, tier: {subscription_tier}")

    # Get or create TaskTracker record
    try:
        user = User.objects.get(id=user_id) if user_id else None
        tracker = TaskTracker.objects.get(task_id=self.request.id)
    except (TaskTracker.DoesNotExist, User.DoesNotExist):
        # Create new tracker if not exists
        tracker = TaskTracker.objects.create(
            task_id=self.request.id,
            task_type=task_type,
            app_id=app_id,
            app_name=app_name or app_id,
            user=user,
            target_reviews=max_reviews,
            status='started'
        )

    # Update task as started
    tracker.update_progress(0, max_reviews, 'started')

    # Load sentiment analysis model
    sentiment_pipeline = pipeline("sentiment-analysis",
                                  model="nlptown/bert-base-multilingual-uncased-sentiment")

    total_new_reviews = 0
    total_skipped_reviews = 0
    total_processed = 0
    continuation_token = None
    page_count = 0

    while total_processed < max_reviews:
        page_count += 1
        remaining_needed = max_reviews - total_processed
        count_for_request = min(REVIEW_COUNT, remaining_needed)

        logger.info(f"Fetching page {page_count}, requesting {count_for_request} reviews...")

        try:
            result, continuation_token = reviews(
                app_id,
                lang='en',
                country=APP_COUNTRY,
                sort=Sort.NEWEST,
                count=count_for_request,
                continuation_token=continuation_token
            )
        except Exception as e:
            logger.error(f"Failed to fetch reviews from Google Play Store on page {page_count}: {e}")
            break

        if not result:
            logger.info(f"No more reviews available after page {page_count}")
            break

        # Process reviews from this page
        page_new_count = 0
        page_skipped_count = 0

        for review_data in result:
            if total_processed >= max_reviews:
                break

            # Calculate sentiment score
            content = review_data.get('content', '') or ''
            if content.strip():
                sentiment_result = sentiment_pipeline(content)
                label = sentiment_result[0]['label']
                if label in ['4 stars', '5 stars']:
                    sentiment_score = sentiment_result[0]['score']
                elif label in ['1 star', '2 stars']:
                    sentiment_score = -sentiment_result[0]['score']
                else:
                    sentiment_score = 0.0
            else:
                rating = review_data.get('score', 3)
                if rating >= 4:
                    sentiment_score = 0.5
                elif rating <= 2:
                    sentiment_score = -0.5
                else:
                    sentiment_score = 0.0

            # Save review
            review_obj, created = Review.objects.get_or_create(
                review_id=review_data['reviewId'],
                defaults={
                    'author': review_data.get('userName', ''),
                    'rating': review_data.get('score', 3),
                    'content': content,
                    'created_at': review_data.get('at'),
                    'source': 'Google Play',
                    'title': '',
                    'sentiment_score': sentiment_score,
                    'app_id': app_id,
                }
            )

            if created:
                page_new_count += 1
                total_new_reviews += 1
            else:
                page_skipped_count += 1
                total_skipped_reviews += 1

        total_processed = total_new_reviews + total_skipped_reviews
        logger.info(f"Page {page_count} complete: {page_new_count} new, {page_skipped_count} duplicates")

        # Update progress - both Celery state AND database tracker
        progress_percent = min(100, int((total_processed / max_reviews) * 100))

        # Update TaskTracker in database for persistent tracking
        tracker.update_progress(total_processed, max_reviews, 'progress')

        # Also update Celery state for immediate feedback
        self.update_state(
            state='PROGRESS',
            meta={
                'current_reviews': total_processed,
                'total_reviews': max_reviews,
                'new_reviews': total_new_reviews,
                'skipped_reviews': total_skipped_reviews,
                'progress_percent': progress_percent,
                'page_count': page_count,
                'app_id': app_id,
                'app_name': tracker.app_name,
                'task_type': tracker.task_type,
                'status': f'Collecting reviews... {total_processed}/{max_reviews}'
            }
        )

        # Stopping conditions
        if total_processed >= max_reviews:
            logger.info(f"Reached target of {max_reviews} reviews")
            break
        if not continuation_token:
            logger.info("No more pages available")
            break
        # More lenient duplicate stopping - only stop if we get NO new reviews on a page
        # and we've collected at least the minimum target, to prevent early termination
        minimum_before_duplicate_stop = int(max_reviews * 0.80) if max_reviews <= 300 else max_reviews - 100
        if page_count > 3 and page_new_count == 0 and total_new_reviews >= minimum_before_duplicate_stop:
            logger.info(f"No new reviews on page {page_count} and collected {total_new_reviews} (minimum: {minimum_before_duplicate_stop}), stopping")
            break
        # Only stop for insufficient results if we haven't reached our minimum target
        # For quick analysis (200 reviews), don't stop early unless we have at least 150
        minimum_for_early_stop = int(max_reviews * 0.75) if max_reviews <= 300 else max_reviews - 100
        if len(result) < count_for_request:
            if total_new_reviews < minimum_for_early_stop:
                logger.info(f"Got {len(result)} but requested {count_for_request}, continuing to reach minimum {minimum_for_early_stop} (currently: {total_new_reviews})")
                # Continue instead of breaking - we need more reviews
            else:
                logger.info(f"Got {len(result)} but requested {count_for_request}, acceptable since we have {total_new_reviews} reviews (minimum: {minimum_for_early_stop})")
                break

    summary = f"Collection complete for {app_id}: {total_new_reviews} new, {total_skipped_reviews} duplicates"
    logger.info(summary)

    # Mark task as completed in database
    tracker.update_progress(total_processed, max_reviews, 'success')
    tracker.result_message = summary
    tracker.save()

    return summary


def import_google_play_reviews_for_user(app_id, user_id=None, subscription_tier='free', quick_analysis=True, app_name=None, project_id=None):
    """
    Progressive disclosure wrapper with proper TaskTracker integration.
    """
    if quick_analysis:
        # Quick analysis: collect 200 reviews for immediate insights (30-second wait)
        review_limit = 200
        task_type = 'quick'
        logger.info(f"Triggering QUICK analysis for user {user_id} ({subscription_tier}) - app: {app_id}, limit: {review_limit}")
    else:
        # Full analysis: collect maximum reviews allowed by subscription
        max_reviews_for_tier = SUBSCRIPTION_REVIEW_LIMITS.get(subscription_tier, SUBSCRIPTION_REVIEW_LIMITS['free'])
        review_limit = min(max_reviews_for_tier, HARD_SYSTEM_MAX_REVIEWS)
        task_type = 'full'
        logger.info(f"Triggering FULL analysis for user {user_id} ({subscription_tier}) - app: {app_id}, limit: {review_limit}")

    # Create TaskTracker record before starting task
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            project = Project.objects.get(id=project_id) if project_id else None

            # Create task first to get the task ID
            task_result = collect_reviews_task.delay(app_id, review_limit, user_id, subscription_tier, app_name, task_type)

            # Create TaskTracker with the actual task ID
            TaskTracker.objects.create(
                task_id=task_result.id,
                task_type=task_type,
                app_id=app_id,
                app_name=app_name or app_id,
                user=user,
                project=project,
                target_reviews=review_limit,
                status='pending'
            )

            return task_result
        except Exception as e:
            logger.error(f"Failed to create TaskTracker: {e}")
            # Fall back to task without tracking
            return collect_reviews_task.delay(app_id, review_limit, user_id, subscription_tier, app_name, task_type)
    else:
        return collect_reviews_task.delay(app_id, review_limit, user_id, subscription_tier, app_name, task_type)


def import_google_play_reviews_full_analysis(app_id, user_id=None, subscription_tier='free'):
    """
    Convenience function for full analysis (remaining reviews after quick analysis).
    """
    return import_google_play_reviews_for_user(app_id, user_id, subscription_tier, quick_analysis=False)

# --- Apple App Store Configuration ---
APPLE_APP_COUNTRY = 'us'


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,), # Use the full path
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=300
)
def import_apple_app_store_reviews(app_id):
    """
    A Celery task to fetch the latest reviews from the Apple App Store RSS feed
    and save them to the database, avoiding duplicates.
    """
    logger.info(f"Starting Apple App Store reviews import for app_id: {app_id}")

    url = f"https://itunes.apple.com/{APPLE_APP_COUNTRY}/rss/customerreviews/page=1/id={app_id}/sortBy=mostRecent/xml"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch reviews from Apple App Store RSS feed: {e}")
        raise

    # CORRECTED: This namespace map now includes the default 'atom' namespace.
    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom',
        'im': 'http://itunes.apple.com/rss'
    }

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML from Apple App Store RSS feed: {e}")
        return "Failed to parse XML."

    new_reviews_count = 0
    skipped_reviews_count = 0

    # Load sentiment analysis model ONCE before the loop
    sentiment_pipeline = pipeline("sentiment-analysis",
                                  model="nlptown/bert-base-multilingual-uncased-sentiment")

    # CORRECTED: We now use the namespace to find the 'atom:entry' tags.
    # We also skip the first entry which is the app title.
    for entry in root.findall('atom:entry', namespaces)[1:]:
        # CORRECTED: All subsequent 'find' calls also use the namespace.
        review_id = entry.find('atom:id', namespaces).text
        author = entry.find('atom:author/atom:name', namespaces).text
        title = entry.find('atom:title', namespaces).text
        content_node = entry.find('atom:content[@type="text"]', namespaces)
        content = content_node.text if content_node is not None else ""
        rating_node = entry.find('im:rating', namespaces)
        rating = int(rating_node.text) if rating_node is not None else 0


        # Get sentiment prediction
        sentiment_result = sentiment_pipeline(content) if content else [{'label': '3 stars', 'score': 0.0}]

        # Convert star ratings to -1 to +1 scale
        label = sentiment_result[0]['label']
        if label in ['4 stars', '5 stars']:  # 4-5 stars = positive
            sentiment_score = sentiment_result[0]['score']
        elif label in ['1 star', '2 stars']:  # 1-2 stars = negative
            sentiment_score = -sentiment_result[0]['score']
        else:  # 3 stars = neutral
            sentiment_score = 0.0

        review_obj, created = Review.objects.get_or_create(
            review_id=review_id,
            defaults={
                'author': author,
                'title': title,
                'content': content,
                'rating': rating,
                'source': 'Apple App Store',
                'sentiment_score': sentiment_score,
            }
        )

        if created:
            new_reviews_count += 1
        else:
            skipped_reviews_count += 1

    summary = (f"Apple import complete. "
               f"New reviews added: {new_reviews_count}. "
               f"Duplicates skipped: {skipped_reviews_count}.")

    logger.info(summary)
    return summary


def extract_pain_points(app_id=None):
    """
    Use LDA topic modeling to discover pain points from negative reviews.
    This replaces the simple keyword matching with actual AI-driven topic discovery.
    """
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation
    import numpy as np

    # Get negative reviews (sentiment < -0.1 to focus on clearly negative ones)
    negative_reviews = Review.objects.filter(sentiment_score__lt=-0.1)

    if app_id:
        negative_reviews = negative_reviews.filter(app_id=app_id)

    if negative_reviews.count() < 10:
        logger.warning(f"Not enough negative reviews ({negative_reviews.count()}) for topic modeling")
        return []

    # Extract review text
    review_texts = [review.content for review in negative_reviews if review.content]

    if len(review_texts) < 10:
        return []

    # Vectorize the text (convert to numbers for LDA)
    vectorizer = CountVectorizer(
        max_features=1000,  # Limit vocabulary size
        stop_words='english',  # Remove common words like "the", "a", "an"
        min_df=2,  # Word must appear in at least 2 documents
        max_df=0.8  # Ignore words that appear in more than 80% of documents
    )

    try:
        doc_term_matrix = vectorizer.fit_transform(review_texts)
    except ValueError as e:
        logger.error(f"Error vectorizing reviews: {e}")
        return []

    # Run LDA to discover topics
    n_topics = 5  # Find top 5 pain point topics
    lda_model = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20,
        n_jobs=-1  # Use all CPU cores
    )

    try:
        lda_model.fit(doc_term_matrix)
    except Exception as e:
        logger.error(f"Error fitting LDA model: {e}")
        return []

    # Extract top words for each topic
    feature_names = vectorizer.get_feature_names_out()
    topics = []

    for topic_idx, topic in enumerate(lda_model.components_):
        # Get top 5 words for this topic
        top_words_idx = topic.argsort()[-5:][::-1]
        top_words = [feature_names[i] for i in top_words_idx]

        # Create a readable topic name from top words
        topic_name = ", ".join(top_words[:3])  # Use top 3 words as name

        # Count how many reviews are primarily about this topic
        doc_topic_distribution = lda_model.transform(doc_term_matrix)
        primary_topic_docs = np.argmax(doc_topic_distribution, axis=1)
        mentions = np.sum(primary_topic_docs == topic_idx)

        if mentions > 0:  # Only include topics with actual mentions
            topics.append({
                'topic_name': topic_name.title(),
                'keywords': top_words,
                'mentions': int(mentions)
            })

    # Sort by number of mentions
    topics.sort(key=lambda x: x['mentions'], reverse=True)

    # Return top 3 pain points
    return topics[:3]


@shared_task
def run_weekly_updates():
    """
    This is the master scheduler task. It finds all projects and triggers
    a background refresh for their 'Home Base' apps.
    """
    logger.info("--- Starting Weekly Scheduled Updates ---")

    # Get all projects from the database
    all_projects = Project.objects.all()

    apps_to_update_count = 0
    for project in all_projects:
        # We need to know if the 'home_base_app' is Apple or Google.
        # This is a simple check. Google App IDs contain a '.'
        if '.' in project.home_app_id:
            # It's a Google Play app
            logger.info(f"Triggering Google Play update for project: {project.name}")
            # We use the existing wrapper function to start the task
            import_google_play_reviews_for_user(
                app_id=project.home_app_id,
                user_id=project.user.id,
                subscription_tier='pro',  # Or get this from the user's profile
                quick_analysis=False,  # We want a full, deep analysis for scheduled updates
                app_name=project.home_app_name,
                project_id=project.id
            )
            apps_to_update_count += 1
        else:
            # It's an Apple App Store app
            logger.info(f"Triggering Apple App Store update for project: {project.name}")
            import_apple_app_store_reviews.delay(app_id=project.home_app_id)
            apps_to_update_count += 1

        # Create daily sentiment snapshots for historical trending
        snapshot_count = 0
        for project in all_projects:
            create_sentiment_snapshot.delay(project.home_app_id)
            logger.info(f"Triggered sentiment snapshot for {project.home_app_name}")
            snapshot_count += 1

        summary = f"Weekly schedule complete. Triggered updates for {apps_to_update_count} 'Home Base' apps. Created {snapshot_count} sentiment snapshots for historical tracking."
        logger.info(summary)

        return summary


# All your existing functions...




@shared_task
def create_sentiment_snapshot(app_id):
    """
    Calculate current sentiment for an app and store as daily snapshot
    """
    from django.utils import timezone
    from .models import Review, SentimentSnapshot
    from datetime import date

    today = date.today()

    # Get all reviews for this app with sentiment scores
    reviews = Review.objects.filter(
        app_id=app_id,
        sentiment_score__isnull=False
    )

    if not reviews.exists():
        return f"No reviews found for {app_id}"

    total_count = reviews.count()
    positive_count = reviews.filter(sentiment_score__gt=0.1).count()
    negative_count = reviews.filter(sentiment_score__lt=-0.1).count()
    neutral_count = total_count - positive_count - negative_count

    # Calculate percentages
    positive_pct = (positive_count / total_count) * 100
    negative_pct = (negative_count / total_count) * 100
    neutral_pct = (neutral_count / total_count) * 100

    # Create or update today's snapshot
    snapshot, created = SentimentSnapshot.objects.update_or_create(
        app_id=app_id,
        date=today,
        defaults={
            'positive_percentage': positive_pct,
            'negative_percentage': negative_pct,
            'neutral_percentage': neutral_pct,
            'total_reviews_analyzed': total_count,
        }
    )

    action = "Created" if created else "Updated"
    return f"{action} snapshot for {app_id}: {positive_pct:.1f}% positive, {negative_pct:.1f}% negative"