# =============================================================================
# >> STEP 1: BOOTSTRAP DJANGO (Same as before)
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
from transformers import pipeline  # The main Hugging Face library


# =============================================================================
# >> STEP 3: THE MAIN ANALYSIS LOGIC
# =============================================================================
def analyze_review_sentiments():
    """
    Analyzes the sentiment of reviews in the database that haven't been processed yet.
    """
    print("Loading sentiment analysis model...")
    # Load a pre-trained sentiment analysis model from Hugging Face.
    # This will download the model the first time you run it (it might take a minute).
    sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

    print("Model loaded. Fetching reviews to analyze...")
    # Fetch only the reviews that don't have a sentiment label yet. This is efficient.
    reviews_to_analyze = Review.objects.filter(sentiment_label__isnull=True)

    if not reviews_to_analyze:
        print("No new reviews to analyze.")
        return

    print(f"Found {len(reviews_to_analyze)} reviews to analyze.")

    # We will process reviews in batches to be more efficient
    review_texts = [review.content for review in reviews_to_analyze]
    results = sentiment_pipeline(review_texts)

    # Now, loop through the original reviews and their corresponding results
    for review, result in zip(reviews_to_analyze, results):
        # The result looks like: {'label': 'POSITIVE', 'score': 0.9998}
        review.sentiment_label = result['label']
        review.sentiment_score = result['score']
        review.save()  # Save the updated review back to the database

    print(f"Successfully analyzed and saved sentiment for {len(reviews_to_analyze)} reviews.")


# =============================================================================
# >> STEP 4: RUN THE SCRIPT
# =============================================================================
if __name__ == "__main__":
    print("Starting sentiment analysis process...")
    analyze_review_sentiments()
    print("Sentiment analysis process finished.")