"""CollectorAgent — RSS収集 + DB重複排除"""

import re
from datetime import datetime, timezone

import feedparser

from scripts.config import RSS_FEEDS, MAX_ITEMS_PER_FEED, MAX_TOTAL_ITEMS, MAJOR_SOURCES
from scripts.db.schema import get_conn

KEYWORDS = [
    "claude", "gpt", "gemini", "chatgpt", "openai", "anthropic",
    "llm", "ai", "midjourney", "copilot", "llama", "sora", "runway",
    "dall-e", "stable diffusion", "generative", "language model",
    "artificial intelligence", "meta ai", "mistral",
]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in KEYWORDS)


def _is_new(url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM articles WHERE url=?", (url,)).fetchone()
    return row is None


def _save(article: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO articles (url, title, source, fetched_at, published_at, status)
            VALUES (:url, :title, :source, :fetched_at, :published_at, 'pending')
        """, article)


def collect():
    """
    Returns:
        articles: 新規取得記事リスト
        has_major: 主要ソース(Anthropic/OpenAI等)の記事が含まれるか
    """
    articles = []
    has_major = False
    now = datetime.now(timezone.utc).isoformat()

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            count = 0
            for entry in feed.entries:
                if count >= MAX_ITEMS_PER_FEED:
                    break
                title   = entry.get("title", "").strip()
                summary = _strip_html(entry.get("summary", ""))[:500]
                url     = entry.get("link", "").strip()
                pub     = entry.get("published", "")

                if not title or not url:
                    continue
                if not _is_relevant(title, summary):
                    continue
                if not _is_new(url):
                    continue

                article = {
                    "url":          url,
                    "title":        title,
                    "summary":      summary,
                    "source":       feed_info["source"],
                    "fetched_at":   now,
                    "published_at": pub,
                }
                _save(article)
                articles.append(article)
                if feed_info["source"] in MAJOR_SOURCES:
                    has_major = True
                count += 1

        except Exception as e:
            print(f"[Collector][WARN] {feed_info['source']}: {e}")

    # 重複URL除去
    seen, unique = set(), []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)

    return unique[:MAX_TOTAL_ITEMS], has_major
