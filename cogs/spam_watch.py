# cogs/spam_watch.py
import re
import time
import discord
from discord.ext import commands

from utils.db import get_log_channel, get_spam_config
from utils.i18n import t as _t

LINK_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

# 길드별 유저 메시지 타임스탬프 버퍼
_msg_buffer: dict[int, dict[int, list[float]]] = {}  # {guild_id: {user_id: [ts,...]}}

# ---- 정책 캐시 (TTL=10초) ----
CACHE_TTL = 10
_spam_cache: dict[int, tuple[float, dict]] = {}  # guild_id -> (expires_ts, conf)

def get_spam_conf_cached(guild_id: int):
    now = time.time()
    hit = _spam_cache.get(guild_id)
    if hit and hit[0] > now:
        return hit[1]
    conf = get_spam_config(guild_id)
    _spam_cache[guild_id] = (now + CACHE_TTL, conf)
    return conf

def invalidate_spam_conf(guild_id: int | None = None):
    if guild_id is None:
        _spam_cache.clear()
    else:
        _spam_cache.pop(guild_id, None)

class SpamWatchCog(commands.Cog):
    """스팸·멘션 폭탄·홍보/피싱 링크 감지"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 정책 변경 즉시 반영
    @commands.Cog.listener()
    async def on_spam_config_updated(self, guild_id: int):
        invalidate_spam_conf(guild_id)

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> bool:
        ch_id = get_log_channel(guild.id)
        if not ch_id:
            return False
        ch = guild.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
        if ch:
            await ch.send(embed=embed)
            return True
        return False

    async def _delete_and_log(self, message: discord.Message, reason_key: str, **fmt):
        try:
            await message.delete()
        except Exception:
            pass

        emb = discord.Embed(
            title=_t(message.guild.id, "log_spam_title"),
            color=0xE53935,
            description=(
                f"**User:** {message.author.mention} (`{message.author}`)\n"
                f"**Channel:** {message.channel.mention}\n"
                f"**Reason:** {_t(message.guild.id, reason_key, **fmt)}"
            ),
        )
        if message.author.display_avatar:
            emb.set_thumbnail(url=message.author.display_avatar.url)
        emb.set_footer(text=_t(message.guild.id, "log_spam_footer_config"))
        await self._send_log(message.guild, emb)

        try:
            await message.author.send(_t(message.guild.id, "dm_spam_notice"))
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_id = message.guild.id
        s = get_spam_conf_cached(guild_id)  # ← 매 메시지마다 정책 교차검증(캐시/DB)

        MAX_MSGS_PER_10S = int(s["max_msgs_per_10s"])
        MAX_MENTIONS_PER_MSG = int(s["max_mentions_per_msg"])
        BLOCK_EVERYONE_HERE = bool(s["block_everyone_here"])
        ENABLE_LINK_FILTER = bool(s["enable_link_filter"])
        WL: list[int] = s.get("everyone_whitelist", [])  # ✅ 화이트리스트

        # ---- 10초당 메시지 속도 제한 ----
        now = time.time()
        gb = _msg_buffer.setdefault(guild_id, {})
        ub = gb.setdefault(message.author.id, [])
        ub.append(now)
        _msg_buffer[guild_id][message.author.id] = [t for t in ub if now - t <= 10]

        if len(_msg_buffer[guild_id][message.author.id]) > MAX_MSGS_PER_10S:
            await self._delete_and_log(
                message, "log_spam_reason_rate",
                count=len(_msg_buffer[guild_id][message.author.id])
            )
            return

        # ---- @everyone/@here 남용 차단 (화이트리스트 면제) ----
        if BLOCK_EVERYONE_HERE and message.mention_everyone:
            author_role_ids = {r.id for r in getattr(message.author, "roles", [])}
            is_whitelisted = any(rid in author_role_ids for rid in WL)
            if not is_whitelisted:
                await self._delete_and_log(message, "log_spam_reason_everyone")
                return

        # ---- 멘션 폭탄 ----
        total_mentions = len(message.mentions) + len(message.role_mentions)
        if total_mentions > MAX_MENTIONS_PER_MSG:
            await self._delete_and_log(
                message, "log_spam_reason_mentions",
                mentions=total_mentions, limit=MAX_MENTIONS_PER_MSG
            )
            return

        # ---- 링크 필터 ----
        if ENABLE_LINK_FILTER:
            content = getattr(message, "content", None)
            if isinstance(content, str) and content:
                if LINK_RE.search(content):
                    lower = content.lower()
                    if any(bad in lower for bad in ("discordgift", "discord-airdrop", "nitrodrop", "grabfree", "t.me")):
                        await self._delete_and_log(message, "log_spam_reason_link")
                        return

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.guild and not after.author.bot:
            await self.on_message(after)

async def setup(bot: commands.Bot):
    await bot.add_cog(SpamWatchCog(bot))
