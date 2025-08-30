import os, json
import psycopg2
from psycopg2.extras import DictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

_conn = None

def get_conn():
    global _conn
    if _conn is None or _conn.closed != 0:
        _conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
        _conn.autocommit = True
    return _conn

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

def get_lockdown_config(guild_id: int) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT lockdown FROM guild_config WHERE guild_id=%s;", (guild_id,))
        row = cur.fetchone()
        base = {
            "enabled": False,
            "min_account_age_hours": 72,
            "min_guild_age_hours": 24,
        }
        if not row or not row["lockdown"]:
            return base
        val = dict(row["lockdown"])
        return {**base, **val}

def set_lockdown_config(guild_id: int, **kwargs):
    allowed = {"enabled", "min_account_age_hours", "min_guild_age_hours"}
    payload = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not payload:
        return
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, lockdown)
            VALUES (%s, %s)
            ON CONFLICT (guild_id)
            DO UPDATE SET lockdown = guild_config.lockdown || EXCLUDED.lockdown;
            """,
            (guild_id, json.dumps(payload)),
        )

def get_panic_state(guild_id: int) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT panic FROM guild_config WHERE guild_id=%s;", (guild_id,))
        row = cur.fetchone()
        base = {"enabled": False, "backup": None}
        if not row or not row["panic"]:
            return base
        val = dict(row["panic"])
        return {**base, **val}

def set_panic_state(guild_id: int, enabled: bool, backup: dict | None):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guild_config (guild_id, panic)
            VALUES (%s, %s)
            ON CONFLICT (guild_id)
            DO UPDATE SET panic = EXCLUDED.panic;
            """,
            (guild_id, json.dumps({"enabled": enabled, "backup": backup})),
        )