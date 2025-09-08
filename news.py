"""Fetch headlines from an RSS feed for display on the matrix."""

from __future__ import annotations

import logging
from typing import List

import feedparser

LOGGER = logging.getLogger(__name__)


class NewsFetcher:
    """Periodically fetch and cache headlines from an RSS feed."""

    def __init__(self, feed_url: str = "https://news.google.com/rss") -> None:
        self.feed_url = feed_url
        self.headlines: List[str] = []

    # ------------------------------------------------------------------
    def set_feed(self, url: str) -> None:
        self.feed_url = url
        LOGGER.debug("News feed set to %s", url)

    # ------------------------------------------------------------------
    def fetch(self) -> None:
        try:
            feed = feedparser.parse(self.feed_url)
            self.headlines = [entry.title for entry in feed.entries[:5]]
            LOGGER.debug("Fetched %d headlines", len(self.headlines))
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Failed to fetch news: %s", exc)
            self.headlines = []

    # ------------------------------------------------------------------
    def headline_string(self) -> str:
        if not self.headlines:
            self.fetch()
        return " | ".join(self.headlines)

