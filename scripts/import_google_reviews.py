# file: scripts/import_google_reviews.py

# =============================================================================
# >> STEP 1: BOOTSTRAP DJANGO
# =============================================================================
import os
import django
import sys


def setup_django():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deepfocal_backend.settings_local')
    django.setup()


setup_django()

# =============================================================================
# >> STEP 2: IMPORT LIBRARIES AND YOUR MODEL
# =============================================================================
from reviews.models import Review
from google_play_scraper import reviews, Sort  # Using the faster 'reviews' function


# =============================================================================
# >> STEP 3: THE MAIN SCRAPING LOGIC
# =============================================================================
def import_google_play_reviews(app_id, lang='en', country='us', num_reviews=200):
    """
    Fetches a specific number of recent customer reviews for a Google Play app
    and saves them to the database.
    """
    print(f"Fetching {num_reviews} reviews for App ID: {app_id} from the {country.upper()} Play Store...")

    try:
        # Using the 'reviews' function to get a fixed count is much faster.
        result, continuation_token = reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=num_reviews  # We specify exactly how many reviews we want
        )

        if not result:
            print("No new reviews found.")
            return

        reviews_saved_count = 0
        for review_data in result:
            author = review_data['userName']
            rating = review_data['score']
            content = review_data['content']

            title_snippet = (content[:75] + '...') if len(content) > 75 else content

            # --- SAVE TO DATABASE ---
            new_review = Review(
                source='Google Play Store',
                author=author,
                rating=rating,
                title=title_snippet,
                content=content
            )
            new_review.save()
            reviews_saved_count += 1

        print(f"Successfully saved {reviews_saved_count} new reviews to the database.")

    except Exception as e:
        print(f"An error occurred: {e}")


# =============================================================================
# >> STEP 4: RUN THE SCRIPT
# =============================================================================
if __name__ == "__main__":
    INSTAGRAM_APP_ID = 'com.instagram.android'

    print("Starting the Google Play import process...")
    import_google_play_reviews(INSTAGRAM_APP_ID)
    print("Import process finished.")