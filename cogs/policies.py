import discord
from discord import app_commands
from discord.ext import commands

from utils.db import (
    upsert_guild,
    get_risk_config, set_risk_config,
    get_spam_config, set_spam_config
)
from utils.i18n import t

class PoliciesCog(commands.Cog):
    """길드별 Risk/Spam 정책을 조회/수정합니다."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="policies", description="Show current policies / 현재 정책 보기")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def policies(self, itx: discord.Interaction):
        upsert_guild(itx.guild_id)
        r = get_risk_config(itx.guild_id)
        s = get_spam_config(itx.guild_id)
        body = t(
            itx.guild_id,
            "policies_body",
            min_age=r["min_account_age_hours"],
            raid_count=r["raid_join_count"],
            raid_win=r["raid_join_window_sec"],
            max_msgs=s["max_msgs_per_10s"],
            max_mentions=s["max_mentions_per_msg"],
            block_eh=t(itx.guild_id, "bool_on") if s["block_everyone_here"] else t(itx.guild_id, "bool_off"),
            link_filter=t(itx.guild_id, "bool_on") if s["enable_link_filter"] else t(itx.guild_id, "bool_off"),
        )
        emb = discord.Embed(title=t(itx.guild_id, "policies_title"), description=body, color=0x546E7A)
        await itx.response.send_message(embed=emb, ephemeral=True)

    @app_commands.command(name="riskset", description="Set risk policy / Risk 정책 설정")
    @app_commands.describe(
        min_account_age_hours="계정 최소 나이(시간)",
        raid_join_window_sec="레이드 판정 윈도(초)",
        raid_join_count="윈도 내 입장 인원"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def riskset(
        self,
        itx: discord.Interaction,
        min_account_age_hours: app_commands.Range[int, 0, 720] | None = None,
        raid_join_window_sec: app_commands.Range[int, 5, 600] | None = None,
        raid_join_count: app_commands.Range[int, 2, 100] | None = None,
    ):
        upsert_guild(itx.guild_id)
        set_risk_config(
            itx.guild_id,
            min_account_age_hours=min_account_age_hours,
            raid_join_window_sec=raid_join_window_sec,
            raid_join_count=raid_join_count,
        )
        await itx.response.send_message(t(itx.guild_id, "riskset_ok"), ephemeral=True)

    @app_commands.command(name="spamset", description="Set spam policy / Spam 정책 설정")
    @app_commands.describe(
        max_msgs_per_10s="10초당 최대 메시지",
        max_mentions_per_msg="1메시지 최대 멘션",
        block_everyone_here="@everyone/@here 차단 여부",
        enable_link_filter="링크 필터 사용 여부(메시지 콘텐츠 인텐트 필요)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def spamset(
        self,
        itx: discord.Interaction,
        max_msgs_per_10s: app_commands.Range[int, 1, 60] | None = None,
        max_mentions_per_msg: app_commands.Range[int, 0, 50] | None = None,
        block_everyone_here: bool | None = None,
        enable_link_filter: bool | None = None,
    ):
        upsert_guild(itx.guild_id)
        set_spam_config(
            itx.guild_id,
            max_msgs_per_10s=max_msgs_per_10s,
            max_mentions_per_msg=max_mentions_per_msg,
            block_everyone_here=block_everyone_here,
            enable_link_filter=enable_link_filter,
        )
        await itx.response.send_message(t(itx.guild_id, "spamset_ok"), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PoliciesCog(bot))
