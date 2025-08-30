import time
import discord
from discord.ext import commands

from utils.db import get_log_channel
from utils.i18n import t

# 기본 임계값 (다음 단계에서 /riskset로 DB설정화 예정)
MIN_ACCOUNT_AGE_HOURS = 72
RAID_JOIN_WINDOW_SEC = 30
RAID_JOIN_COUNT = 5

# 길드별 최근 입장 타임스탬프 버퍼 & 소유자 DM 중복 방지
_recent_joins: dict[int, list[float]] = {}
_owner_dm_cooldown: dict[int, float] = {}  # guild_id -> last_sent_ts
OWNER_DM_COOLDOWN_SEC = 3600  # 1시간에 한 번만 안내 DM

class JoinWatchCog(commands.Cog):
    """신규 유저 입장 시 위험 신호를 감지하고 로그 채널에 경고를 보냅니다."""

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
        # 봇 계정 제외
        if member.bot:
            return

        guild = member.guild
        reasons: list[str] = []

        # 1) 계정 나이 검사
        acct_age_hours = (
            (discord.utils.utcnow() - member.created_at).total_seconds() / 3600
        )
        if acct_age_hours < MIN_ACCOUNT_AGE_HOURS:
            # ko/en 문구는 로그 임베드에서 처리
            reasons.append("new_account")

        # 2) 레이드 의심(단시간 동시 입장 수)
        now = time.time()
        buf = _recent_joins.setdefault(guild.id, [])
        buf.append(now)
        # 윈도 밖 제거
        _recent_joins[guild.id] = [t for t in buf if now - t <= RAID_JOIN_WINDOW_SEC]
        join_count = len(_recent_joins[guild.id])
        if join_count >= RAID_JOIN_COUNT:
            reasons.append("raid_surge")

        # 위험 신호가 없으면 종료
        if not reasons:
            return

        # 유저 DM 공지(가능하면)
        try:
            await member.send(t(guild.id, "dm_join_notice"))
        except Exception:
            pass

        # 로그용 임베드 구성
        reason_str_parts = []
        if "new_account" in reasons:
            reason_str_parts.append(
                t(guild.id, "log_join_reason_new", hours=f"{acct_age_hours:.1f}")
            )
        if "raid_surge" in reasons:
            reason_str_parts.append(
                t(
                    guild.id,
                    "log_join_reason_raid",
                    count=join_count,
                    sec=RAID_JOIN_WINDOW_SEC,
                )
            )
        reason_str = " • ".join(reason_str_parts)

        emb = discord.Embed(
            title=t(guild.id, "log_join_title"),
            color=0xE53935,
            description=(
                f"**User:** {member.mention} (`{member}`)\n"
                f"**Account Created:** {discord.utils.format_dt(member.created_at, style='R')}\n"
                f"**Reason:** {reason_str}"
            ),
        )
        emb.set_thumbnail(url=member.display_avatar.url if member.display_avatar else discord.Embed.Empty)
        emb.set_footer(text=t(guild.id, "log_join_footer_config"))

        sent = await self._send_log(guild, emb)
        if not sent:
            await self._notify_owner_if_no_log(guild)

async def setup(bot: commands.Bot):
    await bot.add_cog(JoinWatchCog(bot))
