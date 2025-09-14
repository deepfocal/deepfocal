from celery import shared_task
from google_play_scraper import reviews, Sort
from .models import Review
import logging
import requests
import xml.etree.ElementTree as ET
logger = logging.getLogger(__name__)

# --- Configuration ---
# In a real app, you'd likely move these to a settings file or a model.
APP_ID = 'com.google.android.apps.maps'
APP_COUNTRY = 'us'
REVIEW_COUNT = 200 # Fetch the 200 most recent reviews

@shared_task(
    autoretry_for=(requests.exceptions.RequestException,), # Use the full path
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=300
)
def import_google_play_reviews():
    """
    A Celery task to fetch the latest reviews from the Google Play Store
    and save them to the database, avoiding duplicates.
    """
    logger.info(f"Starting Google Play reviews import for app_id: {APP_ID}")

    try:
        result, continuation_token = reviews(
            APP_ID,
            lang='en',
            country=APP_COUNTRY,
            sort=Sort.NEWEST,
            count=REVIEW_COUNT
        )
    except Exception as e:
        logger.error(f"Failed to fetch reviews from Google Play Store: {e}")
        # We can re-raise the exception to make the task fail for retry logic later
        raise

    if not result:
        logger.warning("No reviews were fetched from the Google Play Store.")
        return "No reviews fetched."

    new_reviews_count = 0
    skipped_reviews_count = 0

    # This loop contains the "Smart De-duplication" logic
    for review_data in result:
        # get_or_create returns a tuple: (object, created)
        # `created` is a boolean: True if a new object was created, False otherwise.
        review_obj, created = Review.objects.get_or_create(
            review_id=review_data['reviewId'], # The unique field to check
            defaults={ # These fields are only used if a new object is created
                'author': review_data['userName'],
                'rating': review_data['score'],
                'content': review_data['content'],
                'created_at': review_data['at'],
                'source': 'Google Play'
            }
        )

        if created:
            new_reviews_count += 1
        else:
            skipped_reviews_count += 1

    summary = (f"Import complete. "
               f"New reviews added: {new_reviews_count}. "
               f"Duplicates skipped: {skipped_reviews_count}.")

    logger.info(summary)
    return summary

# --- Apple App Store Configuration ---
APPLE_APP_ID = '389801252'  # Instagram - a good test case
APPLE_APP_COUNTRY = 'us'


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,), # Use the full path
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=300
)
def import_apple_app_store_reviews():
    """
    A Celery task to fetch the latest reviews from the Apple App Store RSS feed
    and save them to the database, avoiding duplicates.
    """
    logger.info(f"Starting Apple App Store reviews import for app_id: {APPLE_APP_ID}")

    url = f"https://itunes.apple.com/{APPLE_APP_COUNTRY}/rss/customerreviews/page=1/id={APPLE_APP_ID}/sortBy=mostRecent/xml"

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

        review_obj, created = Review.objects.get_or_create(
            review_id=review_id,
            defaults={
                'author': author,
                'title': title,
                'content': content,
                'rating': rating,
                'source': 'Apple App Store'
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