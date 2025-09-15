# file: validate_app_ids.py
"""
Validate that the app IDs we're using match the actual Google Play Store package names
by checking app details and trying alternative package names
"""

import os
import django
import sys


def setup_django():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
    sys.path.append(project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deepfocal_backend.settings_local')
    django.setup()


setup_django()

from google_play_scraper import app, reviews, Sort


def validate_app_existence():
    """Check if the app IDs we used actually exist and get their details"""

    # Apps that returned zero reviews in our tests
    failed_apps = [
        ('com.any.do', 'Any.do'),
        ('com.appgenix.biztree.todomatrix', 'ToDoMatrix'),
        ('com.youneedabudget.ynab.app', 'YNAB'),
        ('com.headspace.meditation', 'Headspace'),
    ]

    # Alternative app IDs to test for these popular apps
    alternative_ids = {
        'Any.do': [
            'com.anydo',
            'com.any.do.app',
            'com.any.do.android',
            'anydo.android'
        ],
        'YNAB': [
            'com.youneedabudget.ynab',
            'com.ynab.classic',
            'com.youneedabudget.android',
            'youneedabudget.ynab'
        ],
        'Headspace': [
            'com.headspace',
            'com.headspace.app',
            'headspace.meditation',
            'com.headspace.android'
        ],
        'ToDoMatrix': [
            'com.appgenix.biztree.todomatrix',
            'com.todomatrix',
            'todomatrix.android',
            'biztree.todomatrix'
        ]
    }

    print("=== VALIDATING APP IDS ===")
    print("Checking if failed app IDs exist and testing alternatives")
    print("=" * 50)

    for app_id, app_name in failed_apps:
        print(f"\n{'=' * 20} {app_name} {'=' * 20}")

        # Test original app ID
        print(f"Testing original ID: {app_id}")

        try:
            app_info = app(app_id)
            print(f"✓ Original ID exists!")
            print(f"  Title: {app_info.get('title', 'No title')}")
            print(f"  Developer: {app_info.get('developer', 'No developer')}")
            print(f"  Category: {app_info.get('genre', 'No category')}")
            print(f"  Installs: {app_info.get('installs', 'Unknown')}")
            print(f"  Rating: {app_info.get('score', 'No rating')}")
            print(f"  Reviews count: {app_info.get('reviews', 'Unknown')}")

            # If app exists but has no reviews, that explains our zero results
            if app_info.get('reviews') == 0:
                print(f"  ⚠ App has zero reviews - explains our zero results")
            elif app_info.get('reviews', 0) > 0:
                print(f"  ⚠ App claims to have reviews but API returned none - may be access restriction")

        except Exception as e:
            print(f"✗ Original ID failed: {str(e)}")
            print(f"  Testing alternative IDs for {app_name}:")

            # Test alternative IDs
            if app_name in alternative_ids:
                for alt_id in alternative_ids[app_name]:
                    print(f"    Trying: {alt_id}")
                    try:
                        alt_app_info = app(alt_id)
                        print(f"    ✓ Alternative ID works!")
                        print(f"      Title: {alt_app_info.get('title', 'No title')}")
                        print(f"      Reviews: {alt_app_info.get('reviews', 'Unknown')}")

                        # Test if this alternative ID has reviews
                        try:
                            review_result, token = reviews(alt_id, count=10)
                            if review_result:
                                print(f"      ✓ Found {len(review_result)} reviews with this ID!")
                                print(f"      CORRECT ID: {alt_id}")
                                break
                            else:
                                print(f"      No reviews accessible")
                        except:
                            print(f"      Reviews API failed for this ID")

                    except Exception as alt_e:
                        print(f"    ✗ {alt_id}: {str(alt_e)}")
            else:
                print(f"    No alternative IDs defined for {app_name}")


def search_google_play_manually():
    """Manually search for correct app IDs by checking Google Play Store directly"""

    # Let's also test some known working productivity apps to compare
    known_productivity_apps = [
        'com.microsoft.office.outlook',  # Microsoft Outlook
        'com.slack',  # Slack
        'com.notion.id',  # Notion
        'com.atlassian.android.jira.core',  # Jira
        'com.microsoft.teams',  # Microsoft Teams
        'com.asana.app',  # Asana
        'com.dropbox.android',  # Dropbox
        'com.evernote',  # Evernote
    ]

    print(f"\n=== TESTING KNOWN PRODUCTIVITY APPS ===")
    print("Testing popular productivity apps that should definitely have reviews")

    for app_id in known_productivity_apps:
        print(f"\nTesting: {app_id}")

        try:
            # Get app info
            app_info = app(app_id)
            app_title = app_info.get('title', 'Unknown')
            review_count = app_info.get('reviews', 0)

            print(f"  App: {app_title}")
            print(f"  Claimed reviews: {review_count}")

            # Try to get actual reviews
            review_result, token = reviews(app_id, count=50)
            actual_reviews = len(review_result) if review_result else 0

            print(f"  Accessible reviews: {actual_reviews}")

            if actual_reviews > 0:
                print(f"  ✓ SUCCESS - This productivity app has accessible reviews!")
                sample_review = review_result[0]
                print(f"  Sample: '{sample_review.get('content', '')[:80]}...'")
            else:
                print(f"  ✗ No accessible reviews despite claims")

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")


def comprehensive_productivity_test():
    """Test a comprehensive list of productivity apps to see the pattern"""

    productivity_test_apps = [
        # Task Management
        ('com.todoist', 'Todoist'),
        ('com.any.do', 'Any.do'),
        ('com.microsoft.todos', 'Microsoft To Do'),
        ('com.ticktick.task', 'TickTick'),
        ('wunderlist.android', 'Wunderlist'),

        # Note Taking
        ('com.evernote', 'Evernote'),
        ('com.notion.id', 'Notion'),
        ('com.microsoft.office.onenote', 'OneNote'),
        ('md.obsidian', 'Obsidian'),

        # Communication
        ('com.slack', 'Slack'),
        ('com.microsoft.teams', 'Microsoft Teams'),
        ('us.zoom.videomeetings', 'Zoom'),

        # Project Management
        ('com.asana.app', 'Asana'),
        ('com.atlassian.android.jira.core', 'Jira'),
        ('com.monday.monday', 'Monday.com'),
    ]

    print(f"\n=== COMPREHENSIVE PRODUCTIVITY APP TEST ===")
    print("Testing wide range of productivity apps to identify data availability patterns")

    successful_apps = []
    failed_apps = []

    for app_id, app_name in productivity_test_apps:
        print(f"\nTesting {app_name}: {app_id}")

        try:
            # Quick test for reviews
            review_result, token = reviews(app_id, count=10)
            review_count = len(review_result) if review_result else 0

            if review_count > 0:
                print(f"  ✓ {review_count} reviews found")
                successful_apps.append((app_name, app_id, review_count))
            else:
                print(f"  ✗ No reviews found")
                failed_apps.append((app_name, app_id))

        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            failed_apps.append((app_name, app_id))

    # Summary
    print(f"\n=== PRODUCTIVITY APP SUMMARY ===")
    print(f"Successful apps ({len(successful_apps)}):")
    for name, app_id, count in successful_apps:
        print(f"  ✓ {name}: {count} reviews")

    print(f"\nFailed apps ({len(failed_apps)}):")
    for name, app_id in failed_apps:
        print(f"  ✗ {name}")

    success_rate = len(successful_apps) / len(productivity_test_apps) * 100
    print(f"\nProductivity app success rate: {success_rate:.1f}%")

    return successful_apps, failed_apps


if __name__ == "__main__":
    # Step 1: Validate the specific IDs that failed
    validate_app_existence()

    # Step 2: Test known working productivity apps
    search_google_play_manually()

    # Step 3: Comprehensive productivity app test
    comprehensive_productivity_test()