import os
import psycopg2
from psycopg2.extras import DictCursor
import json

DATABASE_URL = os.getenv("DATABASE_URL")

_conn = None

def get_conn():
    global _conn
    if _conn is None or _conn.closed != 0:
        _conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
        _conn.autocommit = True
    return _conn

def _ensure_columns():
    conn = get_conn()
    with conn.cursor() as cur:
        # JSONB 컬럼 추가(없으면)
        cur.execute("ALTER TABLE guild_config ADD COLUMN IF NOT EXISTS risk JSONB;")
        cur.execute("ALTER TABLE guild_config ADD COLUMN IF NOT EXISTS spam JSONB;")
        # 기본값 채우기
        cur.execute("""
        UPDATE guild_config
        SET risk = COALESCE(risk, jsonb_build_object(
            'min_account_age_hours', 72,
            'raid_join_window_sec', 30,
            'raid_join_count', 5
        ));
        """)
        cur.execute("""
        UPDATE guild_config
        SET spam = COALESCE(spam, jsonb_build_object(
            'max_msgs_per_10s', 8,
            'max_mentions_per_msg', 5,
            'block_everyone_here', true,
            'enable_link_filter', false
        ));
        """)

async def init_db():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_config (
              guild_id    BIGINT PRIMARY KEY,
              log_channel BIGINT,
              lang        TEXT NOT NULL DEFAULT 'ko',
              risk        JSONB,
              spam        JSONB
            );
            """
        )
    _ensure_columns()

def upsert_guild(guild_id: int):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guild_config (guild_id)
            VALUES (%s)
            ON CONFLICT (guild_id) DO NOTHING;
            """,
            (guild_id,),
        )

def set_log_channel(guild_id: int, channel_id: int | None):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, log_channel)
            VALUES (%s, %s)
            ON CONFLICT (guild_id)
            DO UPDATE SET log_channel = EXCLUDED.log_channel;
            """,
            (guild_id, channel_id),
        )

def get_log_channel(guild_id: int) -> int | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT log_channel FROM guild_config WHERE guild_id=%s;", (guild_id,))
        row = cur.fetchone()
        return int(row["log_channel"]) if row and row["log_channel"] else None

def set_lang(guild_id: int, lang: str):
    if lang not in ("ko", "en"):
        lang = "ko"
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, lang)
            VALUES (%s, %s)
            ON CONFLICT (guild_id)
            DO UPDATE SET lang = EXCLUDED.lang;
            """,
            (guild_id, lang),
        )

def get_lang(guild_id: int) -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT lang FROM guild_config WHERE guild_id=%s;", (guild_id,))
        row = cur.fetchone()
        return row["lang"] if row and row["lang"] else "ko"

def get_risk_config(guild_id: int) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT risk FROM guild_config WHERE guild_id=%s;", (guild_id,))
        row = cur.fetchone()
        base = {
            "min_account_age_hours": 72,
            "raid_join_window_sec": 30,
            "raid_join_count": 5,
        }
        if not row or not row["risk"]:
            return base
        val = dict(row["risk"])
        return {**base, **val}

def set_risk_config(guild_id: int, **kwargs):
    allowed = {"min_account_age_hours", "raid_join_window_sec", "raid_join_count"}
    payload = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not payload:
        return
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, risk)
            VALUES (%s, %s)
            ON CONFLICT (guild_id)
            DO UPDATE SET risk = guild_config.risk || EXCLUDED.risk;
            """,
            (guild_id, json.dumps(payload)),
        )

def get_spam_config(guild_id: int) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT spam FROM guild_config WHERE guild_id=%s;", (guild_id,))
        row = cur.fetchone()
        base = {
            "max_msgs_per_10s": 8,
            "max_mentions_per_msg": 5,
            "block_everyone_here": True,
            "enable_link_filter": False,
        }
        if not row or not row["spam"]:
            return base
        val = dict(row["spam"])
        return {**base, **val}

def set_spam_config(guild_id: int, **kwargs):
    allowed = {
        "max_msgs_per_10s",
        "max_mentions_per_msg",
        "block_everyone_here",
        "enable_link_filter",
    }
    payload = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not payload:
        return
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, spam)
            VALUES (%s, %s)
            ON CONFLICT (guild_id)
            DO UPDATE SET spam = guild_config.spam || EXCLUDED.spam;
            """,
            (guild_id, json.dumps(payload)),
        )