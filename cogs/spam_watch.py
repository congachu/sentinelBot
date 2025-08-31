# cogs/spam_watch.py
from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import discord
from discord.ext import commands

from utils.db import get_log_channel, get_spam_config
from utils.i18n import t as _t

LINK_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

# 메시지 속도 제한 버퍼
_msg_buffer: dict[int, dict[int, list[float]]] = {}

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

# ── 자동 제재 규칙(요청 사양) ───────────────────────────────
EXTRA_VIOLATIONS_TO_BAN = 10      # 도배/피싱: 임계값 초과 후 추가 10회 → BAN
OVERAGE_RESET_WINDOW_SEC = 1800   # 30분 내 누적, 초과 시 리셋

SEV_EVERYONE_WINDOW = 120.0       # everyone/here: 2분 내
SEV_EVERYONE_COUNT  = 3           # 3회 → BAN

# overage 누적: {gid:{uid:{kind:{'count':int,'first_ts':float}}}}  kind: 'rate' | 'link'
_overage: dict[int, dict[int, dict[str, dict]]] = {}
# everyone 카운터: {gid:{uid:{'everyone':[ts,...]}}}
_violations: dict[int, dict[int, dict[str, list[float]]]] = {}

def _bump_overage(gid: int, uid: int, kind: str) -> bool:
    now = time.time()
    g = _overage.setdefault(gid, {})
    u = g.setdefault(uid, {})
    s = u.setdefault(kind, {"count": 0, "first_ts": now})
    if now - s["first_ts"] > OVERAGE_RESET_WINDOW_SEC:
        s["count"] = 0
        s["first_ts"] = now
    s["count"] += 1
    if s["count"] >= EXTRA_VIOLATIONS_TO_BAN:
        s["count"] = 0
        s["first_ts"] = now
        return True
    return False

async def _escalate_everyone_if_needed(message: discord.Message) -> bool:
    gid, uid = message.guild.id, message.author.id
    now = time.time()
    vg = _violations.setdefault(gid, {})
    vu = vg.setdefault(uid, {})
    arr = vu.setdefault("everyone", [])
    arr.append(now)
    arr[:] = [t for t in arr if now - t <= SEV_EVERYONE_WINDOW]
    if len(arr) >= SEV_EVERYONE_COUNT:
        arr.clear()
        return True
    return False

class SpamWatchCog(commands.Cog):
    """스팸·멘션 폭탄·@everyone/@here 남용·피싱 링크 감지 (요청 조건에서만 자동 제재)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_spam_config_updated(self, guild_id: int):
        invalidate_spam_conf(guild_id)

    # ── 로깅/DM ─────────────────────────────────────────────
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

    # ── 제재 실행(액션 하드코딩) ────────────────────────────
    async def _moderate_user_with_action(self, message: discord.Message, *, action: str, reason_i18n_key: str, **fmt):
        """action: 'kick' | 'ban'  (요청 조건에서만 호출)"""
        guild = message.guild
        member: discord.Member = message.author  # type: ignore
        me: discord.Member = guild.me  # type: ignore

        # 안전장치
        if member == guild.owner or member.top_role >= me.top_role:
            return
        if action == "kick" and not me.guild_permissions.kick_members:
            return
        if action == "ban" and not me.guild_permissions.ban_members:
            return

        rule_reason = _t(guild.id, reason_i18n_key, **fmt)
        final_reason = f"Violation | {rule_reason}"

        try:
            await member.send(_t(guild.id, "dm_mod_notice", action=action.upper(), reason=rule_reason))
        except Exception:
            pass

        if action == "kick":
            try: await member.kick(reason=final_reason)
            except Exception: pass
        elif action == "ban":
            try: await guild.ban(member, reason=final_reason, delete_message_days=0)
            except Exception: pass

        col = 0xC62828 if action == "ban" else 0xEF6C00
        emb = discord.Embed(
            title=_t(guild.id, "log_mod_title"),
            color=col,
            description=(f"**Action:** {action.upper()}\n"
                         f"**User:** {member.mention} (`{member}`)\n"
                         f"**Reason:** {final_reason}")
        )
        if member.display_avatar:
            emb.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(guild, emb)

    # ── 이벤트 핸들러 ───────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_id = message.guild.id
        s = get_spam_conf_cached(guild_id)

        MAX_MSGS_PER_10S = int(s["max_msgs_per_10s"])
        MAX_MENTIONS_PER_MSG = int(s["max_mentions_per_msg"])
        BLOCK_EVERYONE_HERE = bool(s["block_everyone_here"])
        ENABLE_LINK_FILTER = bool(s["enable_link_filter"])
        WL: list[int] = s.get("everyone_whitelist", [])

        # 도배 카운트(10s 윈도)
        now = time.time()
        gb = _msg_buffer.setdefault(guild_id, {})
        ub = gb.setdefault(message.author.id, [])
        ub.append(now)
        gb[message.author.id] = [t for t in ub if now - t <= 10]

        if len(gb[message.author.id]) > MAX_MSGS_PER_10S:
            await self._delete_and_log(message, "log_spam_reason_rate",
                                       count=len(gb[message.author.id]))
            # ⬇️ 추가 10회 누적 시 BAN
            if _bump_overage(guild_id, message.author.id, "rate"):
                await self._moderate_user_with_action(
                    message, action="ban", reason_i18n_key="log_spam_reason_rate",
                    count=len(gb[message.author.id])
                )
            return

        # everyone/here (화이트리스트 제외)
        if BLOCK_EVERYONE_HERE and message.mention_everyone:
            author_role_ids = {r.id for r in getattr(message.author, "roles", [])}
            if not any(rid in author_role_ids for rid in WL):
                await self._delete_and_log(message, "log_spam_reason_everyone")
                # ⬇️ 2분 내 3회면 BAN
                if await _escalate_everyone_if_needed(message):
                    await self._moderate_user_with_action(
                        message, action="ban", reason_i18n_key="log_spam_reason_everyone"
                    )
                return

        # 멘션 과다 → 삭제만
        total_mentions = len(message.mentions) + len(message.role_mentions)
        if total_mentions > MAX_MENTIONS_PER_MSG:
            await self._delete_and_log(
                message, "log_spam_reason_mentions",
                mentions=total_mentions, limit=MAX_MENTIONS_PER_MSG
            )
            return

        # 링크 필터
        if ENABLE_LINK_FILTER:
            content = getattr(message, "content", None)
            if isinstance(content, str) and content:
                urls = LINK_RE.findall(content)
                if urls:
                    PHISHING_KEYWORDS = ("discord-airdrop", "nitrodrop", "grabfree")
                    for url in urls:
                        lower = url.lower()
                        parsed = urlparse(url)
                        host = (parsed.netloc or "").lower()
                        if host == "discord.gift":
                            continue  # 공식 Nitro 선물 허용
                        if ("discordgift" in host) or (host == "t.me") or any(k in lower for k in PHISHING_KEYWORDS):
                            await self._delete_and_log(message, "log_spam_reason_link")
                            # ⬇️ 추가 10회 누적 시 BAN
                            if _bump_overage(guild_id, message.author.id, "link"):
                                await self._moderate_user_with_action(
                                    message, action="ban", reason_i18n_key="log_spam_reason_link"
                                )
                            return

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.guild and not after.author.bot:
            await self.on_message(after)

async def setup(bot: commands.Bot):
    await bot.add_cog(SpamWatchCog(bot))
