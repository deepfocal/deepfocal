from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.conf import settings

from .dashboard_services import build_sentiment_trend, calculate_strategic_scores
from .models import Project
from .topic_modeling import analyze_app_topics


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def project_strategic_scores(request, project_id):
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    scores = calculate_strategic_scores(project)
    return Response(scores)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def project_sentiment_trends(request, project_id):
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

    app_id = request.query_params.get("app_id") or project.home_app_id
    compare_to = request.query_params.get("compare_to") or None
    date_range = request.query_params.get("date_range", "30d")

    data = build_sentiment_trend(project, app_id, compare_to, date_range)
    return Response({"series": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def strengths_insights(request):
    app_id = request.query_params.get("app_id")
    if not app_id:
        return Response({"error": "The 'app_id' query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

    lda_results = analyze_app_topics(app_id, sentiment_filter="positive")
    topics_for_display = lda_results.get("distinct_topics") or lda_results.get("topics", [])
    topic_examples = lda_results.get("topic_examples", {})

    strengths = []
    for idx, topic in enumerate(topics_for_display[:3]):
        examples = topic_examples.get(topic.get("topic_id"), [])
        quotes = [example.get("quote", "").strip() for example in examples if example.get("quote")]

        strengths.append(
            {
                "id": idx + 1,
                "issue": topic.get("label"),
                "keywords": topic.get("top_words", [])[:5],
                "coherence_score": topic.get("coherence_score"),
                "mentions": topic.get("mentions", 0),
                "review_percentage": topic.get("mention_percentage", 0),
                "average_probability": topic.get("average_probability", 0.0),
                "quotes": quotes,
            }
        )

    response_payload = {
        "lda_strengths": strengths,
        "review_count_analyzed": lda_results.get("review_count", 0),
        "raw_review_count": lda_results.get("raw_review_count", lda_results.get("review_count", 0)),
        "filtered_out_reviews": lda_results.get("filtered_out_reviews", 0),
        "app_id": app_id,
        "topic_stats": lda_results.get("topic_stats", {}),
    }

    if lda_results.get("error"):
        response_payload["error"] = lda_results["error"]

    return Response(response_payload)
