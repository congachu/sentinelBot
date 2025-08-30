# cogs/join_watch.py
import time
import discord
from discord.ext import commands

from utils.db import get_log_channel, get_risk_config
from utils.i18n import t as _t   # 👈 t를 _t 별칭으로 임포트

_recent_joins: dict[int, list[float]] = {}
_owner_dm_cooldown: dict[int, float] = {}
OWNER_DM_COOLDOWN_SEC = 3600

class JoinWatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
                f"⚠️ WidowBot: {guild.name} 서버에 로그 채널이 설정되지 않았습니다. "
                f"`/setlog`로 로그 채널을 먼저 지정해주세요."
            )
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        r = get_risk_config(guild.id)
        MIN_ACCOUNT_AGE_HOURS = r["min_account_age_hours"]
        RAID_JOIN_WINDOW_SEC = r["raid_join_window_sec"]
        RAID_JOIN_COUNT = r["raid_join_count"]

        reasons: list[str] = []

        # 1) 계정 나이
        acct_age_hours = (
            (discord.utils.utcnow() - member.created_at).total_seconds() / 3600
        )
        if acct_age_hours < MIN_ACCOUNT_AGE_HOURS:
            reasons.append("new_account")

        # 2) 레이드 의심
        now = time.time()
        buf = _recent_joins.setdefault(guild.id, [])
        buf.append(now)
        # 👇 변수명을 ts로 변경(섀도잉 회피)
        _recent_joins[guild.id] = [ts for ts in buf if now - ts <= RAID_JOIN_WINDOW_SEC]
        join_count = len(_recent_joins[guild.id])
        if join_count >= RAID_JOIN_COUNT:
            reasons.append("raid_surge")

        if not reasons:
            return

        # DM 안내
        try:
            await member.send(_t(guild.id, "dm_join_notice"))
        except Exception:
            pass

        # 로그 임베드
        reason_str_parts = []
        if "new_account" in reasons:
            reason_str_parts.append(
                _t(guild.id, "log_join_reason_new", hours=f"{acct_age_hours:.1f}")
            )
        if "raid_surge" in reasons:
            reason_str_parts.append(
                _t(guild.id, "log_join_reason_raid", count=join_count, sec=RAID_JOIN_WINDOW_SEC)
            )
        reason_str = " • ".join(reason_str_parts)

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
