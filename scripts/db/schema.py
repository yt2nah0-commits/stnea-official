"""SQLite スキーマ初期化"""

import sqlite3
from pathlib import Path
from scripts.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            url           TEXT UNIQUE NOT NULL,
            title         TEXT,
            source        TEXT,
            fetched_at    TEXT,           -- ISO8601
            published_at  TEXT,
            status        TEXT DEFAULT 'pending',
            -- pending / passed / ng / archived / published / queued
            ng_reason     TEXT,
            ng_agent      TEXT,           -- validator / legal
            fixable       INTEGER DEFAULT 0,  -- 1=修正可能
            column_text   TEXT,           -- WriterAgentが生成したコラム本文
            published_at_site TEXT        -- サイト掲載日時
        );

        CREATE TABLE IF NOT EXISTS publish_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            published_at TEXT,
            article_ids  TEXT,            -- JSON配列
            channel      TEXT,            -- site / email / both
            note         TEXT
        );

        CREATE TABLE IF NOT EXISTS ng_archive (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            url        TEXT,
            title      TEXT,
            ng_reason  TEXT,
            ng_agent   TEXT,
            archived_at TEXT,
            fixable     INTEGER
        );
        """)
