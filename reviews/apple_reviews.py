"""Utilities for working with Apple App Store customer reviews."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests

LOGGER = logging.getLogger(__name__)

APPLE_REVIEW_FEED_JSON = "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
APPLE_MAX_FEED_REVIEWS = 100


class AppleReviewError(Exception):
    """Raised when the Apple review feed cannot be fetched or parsed."""


@dataclass
class AppleReview:
    """Structured representation of a single Apple App Store review entry."""

    review_id: str
    author: Optional[str]
    title: Optional[str]
    content: str
    rating: int
    app_version: Optional[str]
    updated: Optional[str]


def _normalise_rating(raw_rating: Optional[str]) -> int:
    try:
        return int(raw_rating or 0)
    except (TypeError, ValueError):
        return 0


def _coerce_text(node: Optional[dict], key: str = "label") -> Optional[str]:
    if not isinstance(node, dict):
        return None
    value = node.get(key)
    return value if isinstance(value, str) else None


def parse_apple_feed_entries(entries: Iterable[dict], max_reviews: int = APPLE_MAX_FEED_REVIEWS) -> List[AppleReview]:
    """Convert raw RSS JSON entries into structured review objects."""

    reviews: List[AppleReview] = []
    for raw in entries:
        review_id = _coerce_text(raw.get("id"))
        if not review_id:
            # Fallback to id.label if nested differently
            review_id = _coerce_text(raw.get("id"), key="label")
        if not review_id:
            continue

        author = _coerce_text(raw.get("author", {}).get("name"))
        title = _coerce_text(raw.get("title"))
        content = (
            _coerce_text(raw.get("content"))
            or _coerce_text(raw.get("summary"))
            or ""
        )
        rating = _normalise_rating(_coerce_text(raw.get("im:rating")))
        version = _coerce_text(raw.get("im:version"))
        updated = _coerce_text(raw.get("updated"))

        reviews.append(
            AppleReview(
                review_id=review_id,
                author=author,
                title=title,
                content=content,
                rating=rating,
                app_version=version,
                updated=updated,
            )
        )

        if len(reviews) >= max_reviews:
            break

    return reviews


def fetch_apple_reviews(
    app_id: str,
    country: str = "us",
    max_reviews: int = APPLE_MAX_FEED_REVIEWS,
    session: Optional[requests.Session] = None,
) -> List[AppleReview]:
    """Fetch reviews from the public Apple RSS feed (JSON flavour)."""

    if max_reviews <= 0:
        return []

    url = APPLE_REVIEW_FEED_JSON.format(country=country.lower(), app_id=app_id)
    http = session or requests.Session()

    LOGGER.debug("Fetching Apple reviews for %s (%s)", app_id, country)

    try:
        response = http.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:  # noqa: BLE001
        LOGGER.error("Failed to fetch Apple review feed: %s", exc)
        raise AppleReviewError(f"Unable to fetch Apple reviews: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:  # noqa: BLE001
        LOGGER.error("Apple review feed returned invalid JSON: %s", exc)
        raise AppleReviewError("Apple review feed returned invalid JSON") from exc

    feed = payload.get("feed", {})
    entries = feed.get("entry", [])
    if not entries or len(entries) <= 1:
        # The first entry is metadata for the app; skip it.
        LOGGER.info("Apple feed contained no review entries for %s", app_id)
        return []

    review_entries = entries[1:]
    return parse_apple_feed_entries(review_entries, max_reviews=max_reviews)
