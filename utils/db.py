import os
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

async def init_db():
    """
    main.py에서 호출됨. 필요한 테이블 생성.
    """
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_config (
              guild_id    BIGINT PRIMARY KEY,
              log_channel BIGINT,
              lang        TEXT NOT NULL DEFAULT 'ko'  -- 'ko' or 'en'
            );
            """
        )

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
