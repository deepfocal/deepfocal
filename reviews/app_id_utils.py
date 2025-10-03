"""Utilities for working with app identifiers across platforms."""
from __future__ import annotations

from typing import Iterable, List, Set

from django.db.models import Q

from .models import CompetitorApp, Project, Review


def expand_app_ids(app_id: str | None) -> List[str]:
    """Return all known identifiers (Google + Apple) linked to *app_id*.

    This includes the provided identifier, the paired identifier on any matching
    project home app, and identifiers stored on competitor records. Results are
    de-duped and empty strings are discarded.
    """
    if not app_id:
        return []

    app_ids: Set[str] = {app_id}

    project_matches = Project.objects.filter(Q(home_app_id=app_id) | Q(apple_app_id=app_id))
    for project in project_matches.only("home_app_id", "apple_app_id"):
        if project.home_app_id:
            app_ids.add(project.home_app_id)
        if project.apple_app_id:
            app_ids.add(project.apple_app_id)

    competitor_matches = CompetitorApp.objects.filter(Q(app_id=app_id) | Q(apple_app_id=app_id))
    for competitor in competitor_matches.only("app_id", "apple_app_id"):
        if competitor.app_id:
            app_ids.add(competitor.app_id)
        if competitor.apple_app_id:
            app_ids.add(competitor.apple_app_id)

    return [value for value in app_ids if value]


def expand_many_app_ids(app_ids: Iterable[str | None]) -> List[str]:
    """Expand and flatten several identifiers into a unique list."""
    combined: Set[str] = set()
    for identifier in app_ids:
        combined.update(expand_app_ids(identifier))
    return [value for value in combined if value]



def get_reviews_for_app_id(app_id: str):
    """Return queryset of reviews for the given identifier across linked IDs."""
    related_ids = expand_app_ids(app_id)
    if not related_ids:
        related_ids = [app_id]
    return Review.objects.filter(app_id__in=related_ids)
