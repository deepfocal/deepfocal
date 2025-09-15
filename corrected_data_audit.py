# file: corrected_data_audit.py
"""
Re-run the data availability audit with corrected app IDs
Based on validation results showing many productivity apps are viable
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

from reviews.tasks import import_google_play_reviews
from reviews.models import Review


def corrected_data_audit():
    """Re-run audit with corrected app IDs and additional validated productivity apps"""

    # Updated test apps with corrected IDs and proven successful apps
    test_apps = [
        # Productivity Apps (CORRECTED AND VALIDATED)
        ('com.todoist', 'Productivity', 'Todoist'),  # Confirmed working
        ('com.anydo', 'Productivity', 'Any.do'),  # CORRECTED: was com.any.do
        ('com.microsoft.todos', 'Productivity', 'Microsoft To Do'),  # Confirmed working
        ('com.ticktick.task', 'Productivity', 'TickTick'),  # Confirmed working
        ('com.microsoft.office.outlook', 'Productivity', 'Microsoft Outlook'),  # 339K reviews
        ('com.evernote', 'Productivity', 'Evernote'),  # 197K reviews
        ('com.microsoft.office.onenote', 'Productivity', 'OneNote'),  # Confirmed working
        ('md.obsidian', 'Productivity', 'Obsidian'),  # Confirmed working

        # Communication & Collaboration (VALIDATED)
        ('com.microsoft.teams', 'Productivity', 'Microsoft Teams'),  # 93K reviews
        ('us.zoom.videomeetings', 'Productivity', 'Zoom'),  # Confirmed working
        ('com.asana.app', 'Productivity', 'Asana'),  # 3K reviews
        ('com.atlassian.android.jira.core', 'Productivity', 'Jira'),  # 887 reviews
        ('com.monday.monday', 'Productivity', 'Monday.com'),  # Confirmed working
        ('com.dropbox.android', 'Productivity', 'Dropbox'),  # 86K reviews

        # Fitness & Health Apps (PREVIOUSLY SUCCESSFUL)
        ('com.alltrails.alltrails', 'Fitness', 'AllTrails'),
        ('com.calm.android', 'Health', 'Calm'),
        ('com.noom.android', 'Health', 'Noom'),

        # Finance Apps (PREVIOUSLY SUCCESSFUL)
        ('com.mint', 'Finance', 'Mint'),
        ('com.personalcapital.pcapandroid', 'Finance', 'Personal Capital'),

        # Education Apps (PREVIOUSLY SUCCESSFUL)
        ('com.duolingo', 'Education', 'Duolingo'),
        ('com.babbel.mobile.android.en', 'Education', 'Babbel'),
        ('com.memrise.android.memrisecompanion', 'Education', 'Memrise'),

        # Entertainment/Media (PREVIOUSLY SUCCESSFUL)
        ('com.spotify.music', 'Music', 'Spotify'),
        ('com.netflix.mediaclient', 'Entertainment', 'Netflix'),
        ('com.pandora.android', 'Music', 'Pandora'),

        # Photography (PREVIOUSLY SUCCESSFUL)
        ('com.adobe.lrmobile', 'Photography', 'Lightroom'),
        ('com.vsco.cam', 'Photography', 'VSCO'),

        # Travel (PREVIOUSLY SUCCESSFUL)
        ('com.airbnb.android', 'Travel', 'Airbnb'),
        ('com.booking', 'Travel', 'Booking.com'),
    ]

    print("=== CORRECTED DEEPFOCAL DATA AVAILABILITY AUDIT ===")
    print(f"Started: {datetime.now()}")
    print("Using validated app IDs with focus on productivity apps")
    print("=" * 60)

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

    # Generate enhanced summary report
    print("\n" + "=" * 60)
    print("=== CORRECTED AUDIT SUMMARY REPORT ===")
    print("=" * 60)

    successful_apps = [r for r in results if r['status'] == 'success']
    apps_with_data = [r for r in results if r['new_reviews'] > 0]
    productivity_apps = [r for r in results if r['category'] == 'Productivity']
    productivity_with_data = [r for r in productivity_apps if r['new_reviews'] > 0]

    print(f"Total apps tested: {len(results)}")
    print(f"Successful imports: {len(successful_apps)}")
    print(f"Apps returning new reviews: {len(apps_with_data)}")
    print(f"Overall success rate: {len(successful_apps) / len(results) * 100:.1f}%")
    print(f"Data availability rate: {len(apps_with_data) / len(results) * 100:.1f}%")

    # PRODUCTIVITY APP FOCUS
    print(f"\n=== PRODUCTIVITY APP PERFORMANCE ===")
    print(f"Productivity apps tested: {len(productivity_apps)}")
    print(f"Productivity apps with data: {len(productivity_with_data)}")
    print(f"Productivity success rate: {len(productivity_with_data) / len(productivity_apps) * 100:.1f}%")

    if apps_with_data:
        avg_reviews = sum(r['new_reviews'] for r in apps_with_data) / len(apps_with_data)
        max_reviews = max(r['new_reviews'] for r in apps_with_data)
        min_reviews = min(r['new_reviews'] for r in apps_with_data if r['new_reviews'] > 0)

        print(f"\nReview volume statistics:")
        print(f"Average reviews per app: {avg_reviews:.1f}")
        print(f"Maximum reviews found: {max_reviews}")
        print(f"Minimum reviews found: {min_reviews}")

        # Productivity-specific stats
        if productivity_with_data:
            prod_avg = sum(r['new_reviews'] for r in productivity_with_data) / len(productivity_with_data)
            prod_total = sum(r['new_reviews'] for r in productivity_with_data)
            print(f"Productivity app average: {prod_avg:.1f} reviews")
            print(f"Total productivity reviews: {prod_total}")

    # Category breakdown with focus on productivity
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
        success_rate = (stats['with_data'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"\n{category}:")
        print(f"  Apps tested: {stats['total']}")
        print(f"  Successful: {stats['success']}/{stats['total']}")
        print(f"  With data: {stats['with_data']}/{stats['total']} ({success_rate:.1f}%)")
        print(f"  Total reviews: {stats['total_reviews']}")

    # Detailed results with productivity emphasis
    print(f"\n=== DETAILED RESULTS ===")

    # Show productivity apps first
    print(f"\nPRODUCTIVITY APPS:")
    for result in results:
        if result['category'] == 'Productivity':
            status_emoji = "✓" if result['status'] == 'success' else "✗"
            data_emoji = "📊" if result['new_reviews'] > 0 else "📭"

            print(f"{status_emoji} {data_emoji} {result['app_name']}")
            print(f"    Reviews: {result['new_reviews']} new, {result['total_reviews']} total")
            print(f"    Time: {result['execution_time']:.2f}s")
            print(f"    Result: {result['result_message']}")

    # Show other categories
    other_categories = set(r['category'] for r in results if r['category'] != 'Productivity')
    for category in sorted(other_categories):
        print(f"\n{category.upper()} APPS:")
        for result in results:
            if result['category'] == category:
                status_emoji = "✓" if result['status'] == 'success' else "✗"
                data_emoji = "📊" if result['new_reviews'] > 0 else "📭"

                print(f"{status_emoji} {data_emoji} {result['app_name']}")
                print(f"    Reviews: {result['new_reviews']} new, {result['total_reviews']} total")
                print(f"    Time: {result['execution_time']:.2f}s")

    print(f"\nCorrected audit completed: {datetime.now()}")

    # Final assessment
    productivity_success = len(productivity_with_data) / len(productivity_apps) * 100 if productivity_apps else 0
    print(f"\n=== STRATEGIC ASSESSMENT ===")
    if productivity_success >= 60:
        print(f"✓ PRODUCTIVITY MARKET VIABLE: {productivity_success:.1f}% success rate")
        print("  Recommendation: Continue with productivity app focus")
    elif productivity_success >= 40:
        print(f"⚠ PRODUCTIVITY MARKET MIXED: {productivity_success:.1f}% success rate")
        print("  Recommendation: Expand to include other high-success categories")
    else:
        print(f"✗ PRODUCTIVITY MARKET CHALLENGING: {productivity_success:.1f}% success rate")
        print("  Recommendation: Consider pivoting to higher-success categories")

    return results


if __name__ == "__main__":
    corrected_data_audit()