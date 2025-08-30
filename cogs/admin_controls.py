# cogs/admin_controls.py
import datetime
import time
import discord
from discord import app_commands
from discord.ext import commands

from utils.db import (
    get_panic_state, set_panic_state,
    get_lockdown_config, set_lockdown_config,
)
from utils.i18n import t as _t

# ===== 정책 캐시 (TTL=10초) =====
CACHE_TTL = 10
_lockdown_cache: dict[int, tuple[float, dict]] = {}  # guild_id -> (expires_ts, conf)

def get_lockdown_conf_cached(guild_id: int) -> dict:
    now = time.time()
    hit = _lockdown_cache.get(guild_id)
    if hit and hit[0] > now:
        return hit[1]
    conf = get_lockdown_config(guild_id)
    _lockdown_cache[guild_id] = (now + CACHE_TTL, conf)
    return conf

def invalidate_lockdown_conf(guild_id: int | None = None):
    if guild_id is None:
        _lockdown_cache.clear()
    else:
        _lockdown_cache.pop(guild_id, None)

def _default_role(guild: discord.Guild) -> discord.Role:
    return guild.default_role  # @everyone

class AdminControls(commands.Cog):
    """패닉/락다운 토글 및 임계값 설정"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===== 외부에서 캐시 무효화 이벤트 받기 =====
    @commands.Cog.listener()
    async def on_lockdown_config_updated(self, guild_id: int):
        invalidate_lockdown_conf(guild_id)

    # ========= Panic =========
    @app_commands.command(name="panic", description="Make all text channels read-only / 모든 텍스트 채널 읽기 전용")
    @app_commands.checks.has_permissions(administrator=True)
    async def panic(self, itx: discord.Interaction):
        guild = itx.guild
        state = get_panic_state(guild.id)
        if state["enabled"]:
            await itx.response.send_message(_t(guild.id, "panic_already_on"), ephemeral=True)
            return

        # 타임아웃 방지
        await itx.response.defer(ephemeral=True, thinking=True)

        backup: dict[str, dict] = {}
        everyone = guild.default_role
        ok_all = True

        text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
        for ch in text_channels:
            try:
                ow = ch.overwrites_for(everyone)
                backup[str(ch.id)] = {"send_messages": ow.send_messages}
                ow.send_messages = False
                await ch.set_permissions(everyone, overwrite=ow, reason="Panic ON")
            except Exception:
                ok_all = False

        set_panic_state(guild.id, True, backup)

        await itx.followup.send(_t(guild.id, "panic_on"))
        if not ok_all:
            await itx.followup.send(_t(guild.id, "panic_partial_warn"))

    @app_commands.command(name="unpanic", description="Restore permissions after panic / 패닉 해제 및 권한 원복")
    @app_commands.checks.has_permissions(administrator=True)
    async def unpanic(self, itx: discord.Interaction):
        guild = itx.guild
        state = get_panic_state(guild.id)
        if not state["enabled"]:
            await itx.response.send_message(_t(guild.id, "panic_already_off"), ephemeral=True)
            return

        await itx.response.defer(ephemeral=True, thinking=True)

        backup = state.get("backup") or {}
        everyone = guild.default_role
        ok_all = True

        for ch_id, data in backup.items():
            ch = guild.get_channel(int(ch_id))
            if not isinstance(ch, discord.TextChannel):
                continue
            try:
                ow = ch.overwrites_for(everyone)
                ow.send_messages = data.get("send_messages", None)
                await ch.set_permissions(everyone, overwrite=ow, reason="Panic OFF")
            except Exception:
                ok_all = False

        set_panic_state(guild.id, False, None)
        await itx.followup.send(_t(guild.id, "panic_off"))
        if not ok_all:
            await itx.followup.send(_t(guild.id, "panic_partial_warn"))

    # ========= Lockdown =========
    @app_commands.command(name="lockdown", description="Toggle lockdown / 락다운 토글")
    @app_commands.describe(enabled="true/false")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def lockdown(self, itx: discord.Interaction, enabled: bool):
        conf = get_lockdown_conf_cached(itx.guild_id)
        if conf["enabled"] == enabled:
            key = "lockdown_already_on" if enabled else "lockdown_already_off"
            await itx.response.send_message(_t(itx.guild_id, key), ephemeral=True)
            return

        set_lockdown_config(itx.guild_id, enabled=enabled)
        # 정책 변경 즉시 반영: 캐시 무효화 이벤트 발행
        self.bot.dispatch("lockdown_config_updated", itx.guild_id)

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
        # 정책 변경 즉시 반영: 캐시 무효화 이벤트 발행
        self.bot.dispatch("lockdown_config_updated", itx.guild_id)

        # 최신 값 조회 후, 다국어 임베드로 응답 (현재값 + 최대 10초 지연 안내)
        l = get_lockdown_config(itx.guild_id)
        desc = (
            f"{_t(itx.guild_id, 'lockdownset_ok')}\n"
            f"{_t(itx.guild_id, 'lockdown_enabled', state=_t(itx.guild_id, 'bool_on') if l['enabled'] else _t(itx.guild_id, 'bool_off'))}\n"
            f"{_t(itx.guild_id, 'lockdown_min_age', hours=l['min_account_age_hours'])}\n"
            f"{_t(itx.guild_id, 'lockdown_min_guild_age', hours=l['min_guild_age_hours'])}\n\n"
            f"{_t(itx.guild_id, 'policy_update_delay')}"
        )
        emb = discord.Embed(title=_t(itx.guild_id, "lockdown_title"), description=desc, color=0x455A64)
        await itx.response.send_message(embed=emb, ephemeral=True)

    # ========= Enforcement (soft) =========
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        conf = get_lockdown_conf_cached(message.guild.id)
        if not conf["enabled"]:
            return

        # 관리자급(메시지 관리 권한)과 봇은 면제
        perms = message.channel.permissions_for(message.author)
        if perms.manage_messages or perms.administrator:
            return

        # 임계값 계산
        now = discord.utils.utcnow()
        acct_age_h = (now - message.author.created_at).total_seconds() / 3600
        joined_at = getattr(message.author, "joined_at", None)
        guild_age_h = (now - joined_at).total_seconds() / 3600 if joined_at else 0

        if acct_age_h < conf["min_account_age_hours"] or guild_age_h < conf["min_guild_age_hours"]:
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
