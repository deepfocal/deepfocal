# file: test_pagination.py
"""
Test pagination with continuation tokens to see if we can get more reviews
from productivity apps that showed zero results in the audit
"""

import os
import django
import sys
import time
from datetime import datetime


def setup_django():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
    sys.path.append(project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deepfocal_backend.settings_local')
    django.setup()


setup_django()

from google_play_scraper import reviews, Sort


def test_pagination_for_productivity_apps():
    """Test pagination on productivity apps that returned zero results"""

    # Focus on productivity apps that failed in the audit
    test_apps = [
        ('com.any.do', 'Any.do'),
        ('com.appgenix.biztree.todomatrix', 'ToDoMatrix'),
        ('com.youneedabudget.ynab.app', 'YNAB'),
        ('com.headspace.meditation', 'Headspace'),  # Also test a health app that failed
    ]

    print("=== PAGINATION TEST FOR LOW-DATA APPS ===")
    print(f"Started: {datetime.now()}")
    print("Testing apps that returned 0 reviews in initial audit")
    print("=" * 60)

    for app_id, app_name in test_apps:
        print(f"\n{'=' * 20} {app_name} {'=' * 20}")
        print(f"App ID: {app_id}")

        total_reviews = []
        page_count = 0
        continuation_token = None
        max_pages = 5  # Limit to prevent infinite loops

        print(f"Starting pagination (max {max_pages} pages)...")

        while page_count < max_pages:
            page_count += 1
            print(f"\nPage {page_count}:")

            try:
                if continuation_token:
                    print(f"  Using continuation token: {str(continuation_token)[:50]}...")
                    # Wait 18 seconds between requests to respect rate limits
                    print("  Waiting 18 seconds for rate limit...")
                    time.sleep(18)

                result, new_token = reviews(
                    app_id,
                    lang='en',
                    country='us',
                    sort=Sort.NEWEST,
                    count=200,
                    continuation_token=continuation_token
                )

                if result and len(result) > 0:
                    print(f"  ✓ Found {len(result)} reviews")
                    total_reviews.extend(result)

                    # Show sample of first and last review from this page
                    first_review = result[0]
                    last_review = result[-1]

                    print(f"  First review date: {first_review.get('at', 'No date')}")
                    print(f"  Last review date: {last_review.get('at', 'No date')}")
                    print(f"  Sample content: '{first_review.get('content', '')[:80]}...'")

                    # Check if we have a continuation token for next page
                    if new_token:
                        print(f"  Continuation token available for next page")
                        continuation_token = new_token
                    else:
                        print(f"  No more pages available")
                        break

                else:
                    print(f"  No reviews found on page {page_count}")
                    break

            except Exception as e:
                print(f"  ✗ Error on page {page_count}: {str(e)}")
                break

        # Summary for this app
        print(f"\n--- {app_name} Summary ---")
        print(f"Total pages retrieved: {page_count}")
        print(f"Total reviews found: {len(total_reviews)}")

        if total_reviews:
            # Analyze the review data
            ratings = [r.get('score', 0) for r in total_reviews if r.get('score')]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0

            # Get date range
            dates = [r.get('at') for r in total_reviews if r.get('at')]
            if dates:
                print(f"Date range: {min(dates)} to {max(dates)}")

            print(f"Average rating: {avg_rating:.1f}/5")

            # Show sentiment distribution preview
            positive_reviews = [r for r in total_reviews if r.get('score', 0) >= 4]
            negative_reviews = [r for r in total_reviews if r.get('score', 0) <= 2]

            print(f"Positive reviews (4-5 stars): {len(positive_reviews)}")
            print(f"Negative reviews (1-2 stars): {len(negative_reviews)}")

            # Sample negative review for pain point analysis
            if negative_reviews:
                sample_negative = negative_reviews[0]
                print(f"Sample negative: '{sample_negative.get('content', '')[:100]}...'")
        else:
            print("No reviews found even with pagination")

        print("-" * 50)

    print(f"\n=== PAGINATION TEST COMPLETE ===")
    print(f"Completed: {datetime.now()}")


def test_single_successful_app_pagination():
    """Test pagination on an app we know has reviews to validate the approach"""

    print(f"\n=== VALIDATION TEST: PAGINATION ON SUCCESSFUL APP ===")

    # Use an app that we know returns 200 reviews to test pagination
    app_id = 'com.spotify.music'
    app_name = 'Spotify'

    print(f"Testing pagination on {app_name} (known to have abundant reviews)")

    total_reviews = []
    page_count = 0
    continuation_token = None
    max_pages = 3  # Just test a few pages

    while page_count < max_pages:
        page_count += 1
        print(f"\nPage {page_count} for {app_name}:")

        try:
            if continuation_token:
                print("  Waiting 18 seconds for rate limit...")
                time.sleep(18)

            result, new_token = reviews(
                app_id,
                lang='en',
                country='us',
                sort=Sort.NEWEST,
                count=200,
                continuation_token=continuation_token
            )

            if result:
                print(f"  ✓ Page {page_count}: {len(result)} reviews")
                total_reviews.extend(result)

                if new_token:
                    continuation_token = new_token
                else:
                    print("  No more pages available")
                    break
            else:
                print(f"  No reviews on page {page_count}")
                break

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            break

    print(f"\n{app_name} pagination result: {len(total_reviews)} total reviews across {page_count} pages")

    if len(total_reviews) > 200:
        print("✓ Pagination successfully retrieved more than 200 reviews!")
        print("This confirms pagination can expand data collection significantly")
    else:
        print("⚠ Pagination did not exceed 200 reviews")


if __name__ == "__main__":
    # First test the apps that showed zero results
    test_pagination_for_productivity_apps()

    # Then validate pagination works on a successful app
    test_single_successful_app_pagination()