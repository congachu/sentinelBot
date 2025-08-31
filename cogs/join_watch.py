# cogs/join_watch.py
from __future__ import annotations
import time
import discord
from discord.ext import commands

from utils.db import get_log_channel, get_risk_config
from utils.i18n import t as _t

_recent_joins: dict[int, list[float]] = {}
_owner_dm_cooldown: dict[int, float] = {}
OWNER_DM_COOLDOWN_SEC = 3600

CACHE_TTL = 10
_risk_cache: dict[int, tuple[float, dict]] = {}

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
    """신규 유저 입장 위험 신호 감지 & 자동 제재 (저연령=Kick / 레이드=Ban)"""

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

    # ── 제재 실행 메서드 ──
    async def _kick_new_account(self, member: discord.Member, acct_age_hours: float):
        guild = member.guild
        me: discord.Member = guild.me  # type: ignore
        if member == guild.owner or member.top_role >= me.top_role:
            return
        if not me.guild_permissions.kick_members:
            return

        reason = _t(guild.id, "log_join_reason_new", hours=f"{acct_age_hours:.1f}")
        final_reason = f"Violation | {reason}"

        try:
            await member.send(_t(guild.id, "dm_mod_notice", action="KICK", reason=reason))
        except Exception:
            pass
        try:
            await member.kick(reason=final_reason)
        except Exception:
            pass

        emb = discord.Embed(
            title=_t(guild.id, "log_mod_title"),
            color=0xEF6C00,
            description=(f"**Action:** KICK\n"
                         f"**User:** {member.mention} (`{member}`)\n"
                         f"**Reason:** {final_reason}")
        )
        if member.display_avatar:
            emb.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(guild, emb)

    async def _ban_raid(self, member: discord.Member, join_count: int, window_sec: int):
        guild = member.guild
        me: discord.Member = guild.me  # type: ignore
        if member == guild.owner or member.top_role >= me.top_role:
            return
        if not me.guild_permissions.ban_members:
            return

        reason = _t(guild.id, "log_join_reason_raid", count=join_count, sec=window_sec)
        final_reason = f"Violation | {reason}"

        try:
            await member.send(_t(guild.id, "dm_mod_notice", action="BAN", reason=reason))
        except Exception:
            pass
        try:
            await guild.ban(member, reason=final_reason, delete_message_days=0)
        except Exception:
            pass

        emb = discord.Embed(
            title=_t(guild.id, "log_mod_title"),
            color=0xC62828,
            description=(f"**Action:** BAN\n"
                         f"**User:** {member.mention} (`{member}`)\n"
                         f"**Reason:** {final_reason}")
        )
        if member.display_avatar:
            emb.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(guild, emb)

    # ── 멤버 입장 감시 ──
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        r = get_risk_conf_cached(guild.id)
        MIN_ACCOUNT_AGE_HOURS = r["min_account_age_hours"]
        RAID_JOIN_WINDOW_SEC = r["raid_join_window_sec"]
        RAID_JOIN_COUNT = r["raid_join_count"]

        acct_age_hours = ((discord.utils.utcnow() - member.created_at).total_seconds() / 3600)

        now = time.time()
        buf = _recent_joins.setdefault(guild.id, [])
        buf.append(now)
        _recent_joins[guild.id] = [ts for ts in buf if now - ts <= RAID_JOIN_WINDOW_SEC]
        join_count = len(_recent_joins[guild.id])

        reasons = []
        if acct_age_hours < MIN_ACCOUNT_AGE_HOURS:
            reasons.append("new_account")
            await self._kick_new_account(member, acct_age_hours)

        if join_count >= RAID_JOIN_COUNT:
            reasons.append("raid_surge")
            await self._ban_raid(member, join_count, RAID_JOIN_WINDOW_SEC)

        if not reasons:
            return

        # 로그 알림
        parts = []
        if "new_account" in reasons:
            parts.append(_t(guild.id, "log_join_reason_new", hours=f"{acct_age_hours:.1f}"))
        if "raid_surge" in reasons:
            parts.append(_t(guild.id, "log_join_reason_raid", count=join_count, sec=RAID_JOIN_WINDOW_SEC))
        reason_str = " • ".join(parts)

        emb = discord.Embed(
            title=_t(guild.id, "log_join_title"),
            color=0xE53935,
            description=(f"**User:** {member.mention} (`{member}`)\n"
                         f"**Account Created:** {discord.utils.format_dt(member.created_at, style='R')}\n"
                         f"**Reason:** {reason_str}")
        )
        if member.display_avatar:
            emb.set_thumbnail(url=member.display_avatar.url)
        emb.set_footer(text=_t(guild.id, "log_join_footer_config"))

        sent = await self._send_log(guild, emb)
        if not sent:
            await self._notify_owner_if_no_log(guild)

async def setup(bot: commands.Bot):
    await bot.add_cog(JoinWatchCog(bot))
