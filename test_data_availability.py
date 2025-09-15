# file: test_data_availability.py
"""
Systematic data audit to test review availability across mid-market apps
Run this to understand the scope of data access limitations
"""

import os
import django
import sys
import time
from datetime import datetime


# Setup Django
def setup_django():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
    sys.path.append(project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'deepfocal_backend.settings_local')
    django.setup()


setup_django()

from reviews.tasks import import_google_play_reviews
from reviews.models import Review

# Test apps across different categories and popularity levels
test_apps = [
    # Productivity Apps
    ('com.todoist', 'Productivity', 'Todoist'),
    ('com.forestapp', 'Productivity', 'Forest'),
    ('com.any.do', 'Productivity', 'Any.do'),
    ('com.appgenix.biztree.todomatrix', 'Productivity', 'ToDoMatrix'),

    # Fitness & Health Apps
    ('com.alltrails.alltrails', 'Fitness', 'AllTrails'),
    ('com.headspace.meditation', 'Health', 'Headspace'),
    ('com.calm.android', 'Health', 'Calm'),
    ('com.noom.android', 'Health', 'Noom'),

    # Finance Apps
    ('com.mint', 'Finance', 'Mint'),
    ('com.youneedabudget.ynab.app', 'Finance', 'YNAB'),
    ('com.personalcapital.pcapandroid', 'Finance', 'Personal Capital'),

    # Education Apps
    ('com.duolingo', 'Education', 'Duolingo'),
    ('com.babbel.mobile.android.en', 'Education', 'Babbel'),
    ('com.memrise.android.memrisecompanion', 'Education', 'Memrise'),

    # Entertainment/Media
    ('com.spotify.music', 'Music', 'Spotify'),
    ('com.netflix.mediaclient', 'Entertainment', 'Netflix'),
    ('com.pandora.android', 'Music', 'Pandora'),

    # Photography
    ('com.adobe.lrmobile', 'Photography', 'Lightroom'),
    ('com.vsco.cam', 'Photography', 'VSCO'),

    # Navigation/Travel
    ('com.airbnb.android', 'Travel', 'Airbnb'),
    ('com.booking', 'Travel', 'Booking.com'),
]


def test_app_data_availability():
    """Test each app and document results"""

    print("=== DEEPFOCAL DATA AVAILABILITY AUDIT ===")
    print(f"Started: {datetime.now()}")
    print("=" * 50)

    results = []

    for app_id, category, app_name in test_apps:
        print(f"\nTesting: {app_name} ({category})")
        print(f"App ID: {app_id}")

        # Record starting review count
        initial_count = Review.objects.filter(app_id=app_id).count()

        start_time = time.time()

        try:
            # Run the import task
            result = import_google_play_reviews.delay(app_id)

            # Wait for task completion (with timeout)
            timeout = 30  # 30 second timeout
            elapsed = 0
            while not result.ready() and elapsed < timeout:
                time.sleep(1)
                elapsed += 1

            if result.ready():
                task_result = result.result
                execution_time = time.time() - start_time

                # Check final review count
                final_count = Review.objects.filter(app_id=app_id).count()
                new_reviews = final_count - initial_count

                print(f"✓ Success: {task_result}")
                print(f"  Execution time: {execution_time:.2f}s")
                print(f"  Reviews found: {new_reviews}")
                print(f"  Total reviews for app: {final_count}")

                results.append({
                    'app_name': app_name,
                    'category': category,
                    'app_id': app_id,
                    'status': 'success',
                    'execution_time': execution_time,
                    'new_reviews': new_reviews,
                    'total_reviews': final_count,
                    'result_message': task_result
                })

            else:
                print(f"✗ Timeout after {timeout}s")
                results.append({
                    'app_name': app_name,
                    'category': category,
                    'app_id': app_id,
                    'status': 'timeout',
                    'execution_time': timeout,
                    'new_reviews': 0,
                    'total_reviews': initial_count,
                    'result_message': 'Task timeout'
                })

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"✗ Error: {str(e)}")
            results.append({
                'app_name': app_name,
                'category': category,
                'app_id': app_id,
                'status': 'error',
                'execution_time': execution_time,
                'new_reviews': 0,
                'total_reviews': initial_count,
                'result_message': str(e)
            })

        # Brief pause between requests
        time.sleep(2)

    # Generate summary report
    print("\n" + "=" * 50)
    print("=== AUDIT SUMMARY REPORT ===")
    print("=" * 50)

    successful_apps = [r for r in results if r['status'] == 'success']
    apps_with_data = [r for r in results if r['new_reviews'] > 0]

    print(f"Total apps tested: {len(results)}")
    print(f"Successful imports: {len(successful_apps)}")
    print(f"Apps returning new reviews: {len(apps_with_data)}")
    print(f"Success rate: {len(successful_apps) / len(results) * 100:.1f}%")
    print(f"Data availability rate: {len(apps_with_data) / len(results) * 100:.1f}%")

    if apps_with_data:
        avg_reviews = sum(r['new_reviews'] for r in apps_with_data) / len(apps_with_data)
        max_reviews = max(r['new_reviews'] for r in apps_with_data)
        min_reviews = min(r['new_reviews'] for r in apps_with_data if r['new_reviews'] > 0)

        print(f"\nReview volume statistics:")
        print(f"Average reviews per app: {avg_reviews:.1f}")
        print(f"Maximum reviews found: {max_reviews}")
        print(f"Minimum reviews found: {min_reviews}")

    # Category breakdown
    print(f"\n=== RESULTS BY CATEGORY ===")
    categories = {}
    for result in results:
        cat = result['category']
        if cat not in categories:
            categories[cat] = {'total': 0, 'success': 0, 'with_data': 0, 'total_reviews': 0}

        categories[cat]['total'] += 1
        if result['status'] == 'success':
            categories[cat]['success'] += 1
        if result['new_reviews'] > 0:
            categories[cat]['with_data'] += 1
            categories[cat]['total_reviews'] += result['new_reviews']

    for category, stats in categories.items():
        print(f"\n{category}:")
        print(f"  Apps tested: {stats['total']}")
        print(f"  Successful: {stats['success']}/{stats['total']}")
        print(f"  With data: {stats['with_data']}/{stats['total']}")
        print(f"  Total reviews: {stats['total_reviews']}")

    # Detailed results
    print(f"\n=== DETAILED RESULTS ===")
    for result in results:
        status_emoji = "✓" if result['status'] == 'success' else "✗"
        data_emoji = "📊" if result['new_reviews'] > 0 else "📭"

        print(f"{status_emoji} {data_emoji} {result['app_name']} ({result['category']})")
        print(f"    Reviews: {result['new_reviews']} new, {result['total_reviews']} total")
        print(f"    Time: {result['execution_time']:.2f}s")
        print(f"    Result: {result['result_message']}")

    print(f"\nAudit completed: {datetime.now()}")

    return results


if __name__ == "__main__":
    test_app_data_availability()