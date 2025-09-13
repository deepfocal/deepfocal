# =============================================================================
# >> STEP 1: BOOTSTRAP DJANGO
# This block of code is the "magic" that allows this standalone script to
# access your Django project's models and database.
# =============================================================================
import os
import django
import sys
import requests
import json


# This function assumes your script is in a 'scripts' folder at the root of your project.
# It finds the root directory and adds it to the Python path.
def setup_django():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(project_root)
    # This line tells Django where to find your project's settings.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deepfocal_backend.settings_local')
    django.setup()


# Call the setup function to initialize Django
setup_django()

# =============================================================================
# >> STEP 2: IMPORT YOUR DJANGO MODEL
# Now that Django is set up, you can import any part of your project.
# We need the 'Review' model to save our data.
# =============================================================================
from reviews.models import Review


# =============================================================================
# >> STEP 3: THE MAIN SCRAPING LOGIC
# This is your original function, but modified to save data to the database.
# =============================================================================
def import_app_store_reviews(app_id, country_code='us'):
    """
    Fetches customer reviews for an Apple App Store app and saves them to the database.
    """

    url = f"https://itunes.apple.com/{country_code}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"

    print(f"Fetching reviews for App ID: {app_id} from the {country_code.upper()} store...")

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        reviews_data = data['feed'].get('entry', [])[1:]

        if not reviews_data:
            print("No new reviews found.")
            return

        reviews_saved_count = 0
        for review_data in reviews_data:
            # Extract the data just like before
            author = review_data['author']['name']['label']
            rating = review_data['im:rating']['label']
            title = review_data['title']['label']
            content = review_data['content']['label']

            # --- THIS IS THE NEW PART ---
            # Instead of printing, we create a new Review object in memory...
            new_review = Review(
                source='Apple App Store',
                author=author,
                rating=int(rating),
                title=title,
                content=content
            )
            # ...and then we save that object as a new row in our database table.
            new_review.save()
            reviews_saved_count += 1

        print(f"Successfully saved {reviews_saved_count} new reviews to the database.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
    except KeyError:
        print("Could not parse the data. The structure of the response may have changed.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


# =============================================================================
# >> STEP 4: RUN THE SCRIPT
# This part stays the same.
# =============================================================================
if __name__ == "__main__":
    INSTAGRAM_APP_ID = '389801252'

    # Call our new function
    print("Starting the import process...")
    import_app_store_reviews(INSTAGRAM_APP_ID)
    print("Import process finished.")