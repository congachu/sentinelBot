# cogs/admin_controls.py
import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils.db import (
    get_panic_state, set_panic_state,
    get_lockdown_config, set_lockdown_config,
)
from utils.i18n import t as _t

def _default_role(guild: discord.Guild) -> discord.Role:
    return guild.default_role  # @everyone

class AdminControls(commands.Cog):
    """패닉/락다운 토글 및 임계값 설정"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========= Panic =========
    @app_commands.command(name="panic", description="Make all text channels read-only / 모든 텍스트 채널 읽기 전용")
    @app_commands.checks.has_permissions(administrator=True)
    async def panic(self, itx: discord.Interaction):
        guild = itx.guild
        state = get_panic_state(guild.id)
        if state["enabled"]:
            await itx.response.send_message(_t(guild.id, "panic_already_on"), ephemeral=True)
            return

        backup: dict[str, dict] = {}
        everyone = _default_role(guild)
        ok_all = True

        # 텍스트 채널만 대상
        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        for ch in text_channels:
            try:
                ow = ch.overwrites_for(everyone)
                # 백업: 기존 값(None/True/False)을 기록
                backup[str(ch.id)] = {"send_messages": ow.send_messages}
                # 차단
                ow.send_messages = False
                await ch.set_permissions(everyone, overwrite=ow, reason="Panic ON")
            except Exception:
                ok_all = False

        set_panic_state(guild.id, True, backup)
        await itx.response.send_message(_t(guild.id, "panic_on"), ephemeral=True)
        if not ok_all:
            await itx.followup.send(_t(guild.id, "panic_partial_warn"), ephemeral=True)

    @app_commands.command(name="unpanic", description="Restore permissions after panic / 패닉 해제 및 권한 원복")
    @app_commands.checks.has_permissions(administrator=True)
    async def unpanic(self, itx: discord.Interaction):
        guild = itx.guild
        state = get_panic_state(guild.id)
        if not state["enabled"]:
            await itx.response.send_message(_t(guild.id, "panic_already_off"), ephemeral=True)
            return

        backup = state.get("backup") or {}
        everyone = _default_role(guild)
        ok_all = True

        for ch_id, data in backup.items():
            ch = guild.get_channel(int(ch_id))
            if not isinstance(ch, discord.TextChannel):
                continue
            try:
                ow = ch.overwrites_for(everyone)
                # 원래 값으로 복구(None/True/False)
                prev = data.get("send_messages", None)
                ow.send_messages = prev
                await ch.set_permissions(everyone, overwrite=ow, reason="Panic OFF")
            except Exception:
                ok_all = False

        # 상태 해제
        set_panic_state(guild.id, False, None)
        await itx.response.send_message(_t(guild.id, "panic_off"), ephemeral=True)
        if not ok_all:
            await itx.followup.send(_t(guild.id, "panic_partial_warn"), ephemeral=True)

    # ========= Lockdown =========
    @app_commands.command(name="lockdown", description="Toggle lockdown / 락다운 토글")
    @app_commands.describe(enabled="true/false")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def lockdown(self, itx: discord.Interaction, enabled: bool):
        conf = get_lockdown_config(itx.guild_id)
        if conf["enabled"] == enabled:
            key = "lockdown_already_on" if enabled else "lockdown_already_off"
            await itx.response.send_message(_t(itx.guild_id, key), ephemeral=True)
            return
        set_lockdown_config(itx.guild_id, enabled=enabled)
        await itx.response.send_message(
            _t(itx.guild_id, "lockdown_on" if enabled else "lockdown_off"),
            ephemeral=True,
        )

    @app_commands.command(name="lockdownset", description="Set lockdown thresholds / 락다운 임계값 설정")
    @app_commands.describe(
        min_account_age_hours="계정 최소 나이(시간)",
        min_guild_age_hours="서버 합류 후 경과 시간(시간)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def lockdownset(
        self,
        itx: discord.Interaction,
        min_account_age_hours: app_commands.Range[int, 0, 720] | None = None,
        min_guild_age_hours: app_commands.Range[int, 0, 720] | None = None,
    ):
        set_lockdown_config(
            itx.guild_id,
            min_account_age_hours=min_account_age_hours,
            min_guild_age_hours=min_guild_age_hours,
        )
        await itx.response.send_message(_t(itx.guild_id, "lockdownset_ok"), ephemeral=True)

    # ========= Enforcement (soft) =========
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        conf = get_lockdown_config(message.guild.id)
        if not conf["enabled"]:
            return

        # 관리자급(메시지 관리 권한)과 봇은 면제
        perms = message.channel.permissions_for(message.author)
        if perms.manage_messages or perms.administrator:
            return

        # 임계값 계산
        now = discord.utils.utcnow()
        acct_age_h = (now - message.author.created_at).total_seconds() / 3600
        # joined_at이 None일 수 있어 방어
        joined_at = getattr(message.author, "joined_at", None)
        guild_age_h = (now - joined_at).total_seconds() / 3600 if joined_at else 0

        if acct_age_h < conf["min_account_age_hours"] or guild_age_h < conf["min_guild_age_hours"]:
            # 메시지 삭제 + DM 공지(실패 무시)
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.author.send(_t(message.guild.id, "msg_blocked_lockdown"))
            except Exception:
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminControls(bot))
