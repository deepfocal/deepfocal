import logging
import requests
import xml.etree.ElementTree as ET
from django.conf import settings
from django.contrib.auth.models import User
from datetime import datetime
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from transformers import pipeline
from celery import shared_task
from googleapiclient.discovery import build
from google_play_scraper import reviews, Sort
from .models import Review, TaskTracker, Project, UserProfile
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
    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error('User %s not found for task tracking', user_id)
            return f'User {user_id} not found for task tracking'
    try:
        tracker = TaskTracker.objects.get(task_id=self.request.id)
    except TaskTracker.DoesNotExist:
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

            raw_timestamp = review_data.get('at')
            if page_count == 1 and page_new_count < 5:
                print(
                    f"[collect_reviews_task] Raw 'at' for {review_data.get('reviewId')}: {raw_timestamp!r} "
                    f"(type={type(raw_timestamp).__name__})"
                )

            review_created_at = raw_timestamp or timezone.now()
            if isinstance(review_created_at, str):
                parsed = parse_datetime(review_created_at)
                if parsed is None:
                    try:
                        parsed = datetime.fromisoformat(review_created_at)
                    except ValueError:
                        parsed = None
                review_created_at = parsed or timezone.now()
            elif isinstance(review_created_at, datetime):
                pass
            else:
                print(
                    f"[collect_reviews_task] Unexpected 'at' type for {review_data.get('reviewId')}: "
                    f"{type(review_created_at).__name__}"
                )
                review_created_at = timezone.now()
            if timezone.is_naive(review_created_at):
                review_created_at = timezone.make_aware(review_created_at)

            # Save review
            review_obj, created = Review.objects.get_or_create(
                review_id=review_data['reviewId'],
                defaults={
                    'author': review_data.get('userName', ''),
                    'rating': review_data.get('score', 3),
                    'content': content,
                    'created_at': review_created_at,
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
                update_fields = []
                if review_obj.created_at != review_created_at:
                    review_obj.created_at = review_created_at
                    update_fields.append('created_at')
                if review_obj.sentiment_score != sentiment_score:
                    review_obj.sentiment_score = sentiment_score
                    update_fields.append('sentiment_score')
                if update_fields:
                    review_obj.save(update_fields=update_fields)
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

APPLE_SUBSCRIPTION_REVIEW_LIMITS = {
    'free': 200,
    'starter': 500,
    'pro': 500,
    'enterprise': 1000,
}



@shared_task
def import_web_mentions(app_name, max_results=30):
    """Collect recent web mentions via Google Custom Search and store as reviews."""
    if not app_name:
        logger.warning('import_web_mentions called without app_name')
        return 'No app name provided.'

    api_key = getattr(settings, 'GOOGLE_SEARCH_API_KEY', None)
    search_engine_id = getattr(settings, 'GOOGLE_SEARCH_ENGINE_ID', None)

    if not api_key or not search_engine_id:
        logger.error('Google Custom Search credentials are missing.')
        return 'Missing Google Custom Search credentials.'

    query = f"\"{app_name}\" review OR feedback"

    try:
        service = build('customsearch', 'v1', developerKey=api_key, cache_discovery=False)
        service._http.timeout = 10
        all_items = []
        for page in range(3):
            start_index = (page * 10) + 1
            response = service.cse().list(
                q=query,
                cx=search_engine_id,
                num=10,
                start=start_index
            ).execute()

            items = response.get('items')
            if not items:
                break
            all_items.extend(items)

        if not all_items:
            logger.info('No web mentions found for %s', app_name)
            return 'No web mentions found.'

    except Exception as exc:
        logger.error('Google Custom Search API request failed for %s: %s', app_name, exc)
        return f'Mention import failed: {exc}'

    sentiment_pipeline = pipeline(
        'sentiment-analysis',
        model='nlptown/bert-base-multilingual-uncased-sentiment'
    )

    new_count = 0
    skipped = 0

    for item in all_items[:max_results]:
        link = item.get('link')
        if not link:
            continue

        title = (item.get('title') or '').strip()
        snippet = (item.get('snippet') or '').strip()
        combined_content = "\n".join(filter(None, [title, snippet]))

        if combined_content:
            truncated_content = combined_content[:500]
            sentiment_result = sentiment_pipeline(truncated_content)
            label = sentiment_result[0]['label']
            score = sentiment_result[0]['score']
            if label in ['4 stars', '5 stars']:
                sentiment_score = score
            elif label in ['1 star', '2 stars']:
                sentiment_score = -score
            else:
                sentiment_score = 0.0
        else:
            sentiment_score = 0.0

        defaults = {
            'author': '',
            'title': title,
            'content': combined_content or title,
            'rating': 3,
            'source': 'Web Search',
            'sentiment_score': sentiment_score,
            'app_id': app_name,
            'counts_toward_score': False,
            'created_at': timezone.now(),
        }

        _, created = Review.objects.update_or_create(
            review_id=link,
            defaults=defaults
        )

        if created:
            new_count += 1
        else:
            skipped += 1

    summary = (
        f"Web mention import complete for {app_name}. "
        f"New mentions: {new_count}. Existing: {skipped}."
    )
    logger.info(summary)
    return summary


@shared_task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=300
)
def import_reddit_mentions(app_name, max_results=100):
    """Import relevant Reddit posts and comments as supplementary review data."""
    if not app_name:
        logger.warning('import_reddit_mentions called without app_name')
        return 'No app name provided.'

    headers = {'User-Agent': 'Deepfocal/1.0'}
    sentiment_pipeline = pipeline(
        'sentiment-analysis',
        model='nlptown/bert-base-multilingual-uncased-sentiment',
        truncation=True,
        max_length=512
    )

    total_posts = 0
    total_comments = 0
    new_mentions = 0
    updated_mentions = 0

    def _sentiment_score(text: str) -> float:
        truncated_text = text[:500]
        result = sentiment_pipeline(truncated_text)
        label = result[0]['label']
        score = result[0]['score']
        if label in ['4 stars', '5 stars']:
            return score
        if label in ['1 star', '2 stars']:
            return -score
        return 0.0

    def _timestamp_from_utc(value):
        try:
            ts = float(value)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return timezone.now()

    search_params = {
        'q': app_name,
        'sort': 'relevance',
        'limit': max_results,
        't': 'year',
        'restrict_sr': False,
    }

    try:
        response = requests.get('https://www.reddit.com/search.json', headers=headers, params=search_params, timeout=10)
        response.raise_for_status()
        search_payload = response.json()
    except Exception as exc:
        logger.error('Failed to search Reddit for %s: %s', app_name, exc)
        return f'Reddit search failed: {exc}'

    posts = search_payload.get('data', {}).get('children', [])
    normalized_app = app_name.lower()

    for post_wrapper in posts:
        if post_wrapper.get('kind') != 't3':
            continue

        post = post_wrapper.get('data', {})
        title = (post.get('title') or '').strip()
        body = (post.get('selftext') or '').strip()
        content_parts = [part for part in [title, body] if part]
        if not content_parts:
            continue

        content = '\n\n'.join(content_parts)
        if normalized_app not in content.lower():
            continue

        sentiment = _sentiment_score(content)

        permalink = post.get('permalink') or ''
        review_id = f'https://www.reddit.com{permalink}' if permalink else f"reddit:post:{post.get('id')}"
        created_at = _timestamp_from_utc(post.get('created_utc'))

        defaults = {
            'author': post.get('author') or '',
            'title': title,
            'content': content,
            'rating': 3,
            'source': 'Reddit',
            'sentiment_score': sentiment,
            'app_id': app_name,
            'counts_toward_score': False,
            'created_at': created_at,
        }

        _, created = Review.objects.update_or_create(
            review_id=review_id,
            defaults=defaults
        )
        total_posts += 1
        if created:
            new_mentions += 1
        else:
            updated_mentions += 1

        if not permalink:
            continue

        comments_url = f'https://www.reddit.com{permalink}.json'
        comment_params = {'limit': 3, 'depth': 1, 'sort': 'top'}
        try:
            comments_response = requests.get(
                comments_url,
                headers=headers,
                params=comment_params,
                timeout=10
            )
            comments_response.raise_for_status()
            comments_payload = comments_response.json()
        except Exception as exc:
            logger.error('Failed to fetch comments for %s: %s', review_id, exc)
            continue

        if not isinstance(comments_payload, list) or len(comments_payload) < 2:
            continue

        comments_data = comments_payload[1].get('data', {}).get('children', [])
        processed_comments = 0
        for comment_wrapper in comments_data:
            if comment_wrapper.get('kind') != 't1':
                continue

            comment = comment_wrapper.get('data', {})
            body_text = (comment.get('body') or '').strip()
            if not body_text:
                continue

            if normalized_app not in body_text.lower():
                continue

            comment_permalink = comment.get('permalink') or ''
            comment_review_id = (
                f'https://www.reddit.com{comment_permalink}'
                if comment_permalink else f"reddit:comment:{comment.get('id')}"
            )

            comment_defaults = {
                'author': comment.get('author') or '',
                'title': f"Comment on {title}" if title else 'Reddit comment',
                'content': body_text,
                'rating': 3,
                'source': 'Reddit',
                'sentiment_score': _sentiment_score(body_text),
                'app_id': app_name,
                'counts_toward_score': False,
                'created_at': _timestamp_from_utc(comment.get('created_utc')),
            }

            _, comment_created = Review.objects.update_or_create(
                review_id=comment_review_id,
                defaults=comment_defaults
            )
            total_comments += 1
            if comment_created:
                new_mentions += 1
            else:
                updated_mentions += 1

            processed_comments += 1
            if processed_comments >= 3:
                break

    summary = (
        f"Reddit import complete for {app_name}. Posts processed: {total_posts}. "
        f"Comments processed: {total_comments}. New mentions: {new_mentions}. "
        f"Updated mentions: {updated_mentions}."
    )
    logger.info(summary)
    return summary


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=300
)
def import_apple_app_store_reviews(app_id, user_id=None, subscription_tier='free', app_name=None, project_id=None):
    """
    Fetch recent Apple App Store reviews via the public RSS feed and persist them.
    """
    if not app_id:
        logger.warning("No Apple App Store app_id provided; skipping import.")
        return "No Apple App Store app_id provided."

    logger.info(
        "Starting Apple App Store reviews import for app_id=%s (user_id=%s, tier=%s)",
        app_id,
        user_id,
        subscription_tier,
    )

    review_limit = APPLE_SUBSCRIPTION_REVIEW_LIMITS.get(
        subscription_tier,
        APPLE_SUBSCRIPTION_REVIEW_LIMITS['free'],
    )

    url = (
        f"https://itunes.apple.com/{APPLE_APP_COUNTRY}/rss/customerreviews/page=1/"
        f"id={app_id}/sortBy=mostRecent/xml"
    )

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error(
            "Failed to fetch reviews from Apple App Store RSS feed for %s: %s",
            app_id,
            exc,
        )
        raise

    print('[apple_import] RAW RSS snippet:', response.text[:1000])

    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom',
        'im': 'http://itunes.apple.com/rss',
    }

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        logger.error("Failed to parse XML from Apple App Store RSS feed for %s: %s", app_id, exc)
        return "Failed to parse XML."

    entries = root.findall('atom:entry', namespaces)
    if len(entries) <= 1:
        logger.info("No Apple App Store review entries found for %s", app_id)
        return "No Apple App Store reviews found."

    sentiment_pipeline = pipeline(
        "sentiment-analysis",
        model="nlptown/bert-base-multilingual-uncased-sentiment",
        truncation=True,
        max_length=512,
    )

    new_reviews_count = 0
    skipped_reviews_count = 0
    total_processed = 0
    debug_sample_limit = 3
    debug_sample_index = 0

    for entry in entries[1:]:
        if total_processed >= review_limit:
            break

        if debug_sample_index < debug_sample_limit:
            entry_xml = ET.tostring(entry, encoding='unicode')
            print('[apple_import] Entry XML snippet:', entry_xml[:500])

        review_id_node = entry.find('atom:id', namespaces)
        if review_id_node is None or not review_id_node.text:
            continue
        review_id = review_id_node.text.strip()

        author_node = entry.find('atom:author/atom:name', namespaces)
        author = (author_node.text or '').strip() if author_node is not None else ''

        title_node = entry.find('atom:title', namespaces)
        title = (title_node.text or '').strip() if title_node is not None else ''

        content_node = entry.find('atom:content[@type="text"]', namespaces)
        content = (content_node.text or '').strip() if content_node is not None else ''

        rating_node = entry.find('im:rating', namespaces)
        try:
            rating = int(rating_node.text) if rating_node is not None and rating_node.text else 0
        except ValueError:
            rating = 0

        timestamp_node = (
            entry.find('atom:updated', namespaces)
            or entry.find('atom:published', namespaces)
            or entry.find('im:releaseDate', namespaces)
        )
        raw_timestamp = timestamp_node.text if timestamp_node is not None else None
        if debug_sample_index < debug_sample_limit:
            print('[apple_import] raw timestamp string:', raw_timestamp)
        review_created_at = raw_timestamp or timezone.now()

        if isinstance(review_created_at, str):
            parsed = parse_datetime(review_created_at)
            if debug_sample_index < debug_sample_limit:
                print('[apple_import] parsed timestamp:', parsed)
            if parsed is None:
                try:
                    parsed = datetime.fromisoformat(review_created_at)
                except ValueError:
                    parsed = None
            review_created_at = parsed or timezone.now()
        elif isinstance(review_created_at, datetime):
            pass
        else:
            review_created_at = timezone.now()

        if timezone.is_naive(review_created_at):
            review_created_at = timezone.make_aware(review_created_at)

        if debug_sample_index < debug_sample_limit:
            print('[apple_import] final created_at:', review_created_at)
            debug_sample_index += 1

        if content:
            sentiment_result = sentiment_pipeline(content)
            label = sentiment_result[0]['label']
            if label in ['4 stars', '5 stars']:
                sentiment_score = sentiment_result[0]['score']
            elif label in ['1 star', '2 stars']:
                sentiment_score = -sentiment_result[0]['score']
            else:
                sentiment_score = 0.0
        else:
            if rating >= 4:
                sentiment_score = 0.5
            elif rating and rating <= 2:
                sentiment_score = -0.5
            else:
                sentiment_score = 0.0

        defaults = {
            'author': author,
            'title': title,
            'content': content,
            'rating': rating,
            'source': 'Apple App Store',
            'sentiment_score': sentiment_score,
            'app_id': app_id,
            'created_at': review_created_at,
            'counts_toward_score': True,
        }

        review_obj, created = Review.objects.get_or_create(
            review_id=review_id,
            defaults=defaults,
        )

        if created:
            new_reviews_count += 1
        else:
            update_fields = []
            if review_obj.author != author:
                review_obj.author = author
                update_fields.append('author')
            if review_obj.title != title:
                review_obj.title = title
                update_fields.append('title')
            if review_obj.content != content:
                review_obj.content = content
                update_fields.append('content')
            if review_obj.rating != rating:
                review_obj.rating = rating
                update_fields.append('rating')
            if review_obj.sentiment_score != sentiment_score:
                review_obj.sentiment_score = sentiment_score
                update_fields.append('sentiment_score')
            if review_obj.app_id != app_id:
                review_obj.app_id = app_id
                update_fields.append('app_id')
            if review_obj.created_at != review_created_at:
                review_obj.created_at = review_created_at
                update_fields.append('created_at')
            if not review_obj.counts_toward_score:
                review_obj.counts_toward_score = True
                update_fields.append('counts_toward_score')

            if update_fields:
                review_obj.save(update_fields=update_fields)

            skipped_reviews_count += 1

        total_processed += 1

    summary = (
        "Apple import complete. "
        f"Processed {total_processed} reviews (limit {review_limit}). "
        f"New reviews added: {new_reviews_count}. Duplicates skipped: {skipped_reviews_count}."
    )
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

    all_projects = Project.objects.all()

    apps_to_update_count = 0
    for project in all_projects:
        profile = UserProfile.objects.get_or_create(user=project.user)[0]

        if project.home_app_id:
            logger.info(f"Triggering Google Play update for project: {project.name}")
            import_google_play_reviews_for_user(
                app_id=project.home_app_id,
                user_id=project.user.id,
                subscription_tier=profile.subscription_tier,
                quick_analysis=False,
                app_name=project.home_app_name,
                project_id=project.id
            )
            apps_to_update_count += 1

        if project.apple_app_id:
            logger.info(f"Triggering Apple App Store update for project: {project.name}")
            import_apple_app_store_reviews.delay(
                app_id=project.apple_app_id,
                user_id=project.user.id,
                subscription_tier=profile.subscription_tier,
                app_name=project.home_app_name,
                project_id=project.id
            )
            apps_to_update_count += 1

    summary = (
        "Weekly schedule complete. Triggered updates for "
        f"{apps_to_update_count} 'Home Base' apps."
    )
    logger.info(summary)

    return summary

# All your existing functions...
