# cogs/join_watch.py
from __future__ import annotations

import time
import discord
from discord.ext import commands

from utils.db import get_log_channel, get_risk_config, get_enforce_config
from utils.i18n import t as _t

# 최근 입장 버퍼 & DM 쿨다운
_recent_joins: dict[int, list[float]] = {}
_owner_dm_cooldown: dict[int, float] = {}
OWNER_DM_COOLDOWN_SEC = 3600

# ---- 정책 캐시 (TTL=10초) ----
CACHE_TTL = 10
_risk_cache: dict[int, tuple[float, dict]] = {}  # guild_id -> (expires_ts, conf)

def get_risk_conf_cached(guild_id: int):
    now = time.time()
    hit = _risk_cache.get(guild_id)
    if hit and hit[0] > now:
        return hit[1]
    conf = get_risk_config(guild_id)
    _risk_cache[guild_id] = (now + CACHE_TTL, conf)
    return conf

def invalidate_risk_conf(guild_id: int | None = None):
    if guild_id is None:
        _risk_cache.clear()
    else:
        _risk_cache.pop(guild_id, None)


class JoinWatchCog(commands.Cog):
    """신규 유저 입장 위험 신호 감지 & 로그 (+ 레이드+저연령 즉시 킥)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_risk_config_updated(self, guild_id: int):
        invalidate_risk_conf(guild_id)

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> bool:
        ch_id = get_log_channel(guild.id)
        if not ch_id:
            return False
        ch = guild.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
        if ch:
            await ch.send(embed=embed)
            return True
        return False

    async def _notify_owner_if_no_log(self, guild: discord.Guild):
        now = time.time()
        last = _owner_dm_cooldown.get(guild.id, 0)
        if now - last < OWNER_DM_COOLDOWN_SEC:
            return
        _owner_dm_cooldown[guild.id] = now
        try:
            owner = guild.owner or await guild.fetch_owner()
            await owner.send(
                f"⚠️ SentinelBot: {guild.name} 서버에 로그 채널이 설정되지 않았습니다. `/setlog`로 먼저 지정하세요."
            )
        except Exception:
            pass

    async def _kick_raid_young(self, member: discord.Member, *, acct_age_hours: float,
                               join_count: int, window_sec: int):
        """레이드 확정 + 저연령 계정 → 정책이 ban이어도 '킥'으로만 처리"""
        guild = member.guild
        me: discord.Member = guild.me  # type: ignore
        if member == guild.owner or member.top_role >= me.top_role:
            return
        if not me.guild_permissions.kick_members:
            return

        e = get_enforce_config(guild.id)  # reason 재사용
        # 사유 구성: 정책 reason + (레이드/저연령 설명)
        rule_reason = (
            _t(guild.id, "log_join_reason_raid", count=join_count, sec=window_sec)
            + " | "
            + _t(guild.id, "log_join_reason_new", hours=f"{acct_age_hours:.1f}")
        )
        final_reason = f"{(e.get('reason') or 'Violation')} | {rule_reason}"

        # DM 안내
        try:
            await member.send(_t(guild.id, "dm_mod_notice", action="KICK", reason=rule_reason))
        except Exception:
            pass

        # 킥 실행
        try:
            await member.kick(reason=final_reason)
        except Exception:
            pass

        # 제재 로그
        emb = discord.Embed(
            title=_t(guild.id, "log_mod_title"),
            color=0xEF6C00,
            description=(
                f"**Action:** KICK\n"
                f"**User:** {member.mention} (`{member}`)\n"
                f"**Reason:** {final_reason}"
            ),
        )
        if member.display_avatar:
            emb.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(guild, emb)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        r = get_risk_conf_cached(guild.id)
        MIN_ACCOUNT_AGE_HOURS = r["min_account_age_hours"]
        RAID_JOIN_WINDOW_SEC = r["raid_join_window_sec"]
        RAID_JOIN_COUNT = r["raid_join_count"]

        reasons = []

        # 계정 나이
        acct_age_hours = ((discord.utils.utcnow() - member.created_at).total_seconds() / 3600)
        if acct_age_hours < MIN_ACCOUNT_AGE_HOURS:
            reasons.append("new_account")

        # 레이드 급증 감지
        now = time.time()
        buf = _recent_joins.setdefault(guild.id, [])
        buf.append(now)
        _recent_joins[guild.id] = [ts for ts in buf if now - ts <= RAID_JOIN_WINDOW_SEC]
        join_count = len(_recent_joins[guild.id])
        if join_count >= RAID_JOIN_COUNT:
            reasons.append("raid_surge")

        # 레이드 + 저연령 → 즉시 킥 (정책이 ban이어도 킥으로만)
        if "raid_surge" in reasons and acct_age_hours < MIN_ACCOUNT_AGE_HOURS:
            await self._kick_raid_young(
                member,
                acct_age_hours=acct_age_hours,
                join_count=join_count,
                window_sec=RAID_JOIN_WINDOW_SEC,
            )

        # 로그/DM (정보 전달은 계속 수행)
        if not reasons:
            return

        try:
            await member.send(_t(guild.id, "dm_join_notice"))
        except Exception:
            pass

        parts = []
        if "new_account" in reasons:
            parts.append(_t(guild.id, "log_join_reason_new", hours=f"{acct_age_hours:.1f}"))
        if "raid_surge" in reasons:
            parts.append(_t(guild.id, "log_join_reason_raid", count=join_count, sec=RAID_JOIN_WINDOW_SEC))
        reason_str = " • ".join(parts)

        emb = discord.Embed(
            title=_t(guild.id, "log_join_title"),
            color=0xE53935,
            description=(
                f"**User:** {member.mention} (`{member}`)\n"
                f"**Account Created:** {discord.utils.format_dt(member.created_at, style='R')}\n"
                f"**Reason:** {reason_str}"
            ),
        )
        if member.display_avatar:
            emb.set_thumbnail(url=member.display_avatar.url)
        emb.set_footer(text=_t(guild.id, "log_join_footer_config"))

        sent = await self._send_log(guild, emb)
        if not sent:
            await self._notify_owner_if_no_log(guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(JoinWatchCog(bot))
