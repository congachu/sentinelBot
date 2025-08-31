# cogs/modlog.py
from __future__ import annotations
import discord
from discord.ext import commands
from utils.db import get_log_channel
from utils.i18n import t as _t

class ModLogCog(commands.Cog):
    """BAN/UNBAN 등 주요 제재 이벤트 로깅"""

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

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        # 감사 로그에서 실행자/사유 추출 (권한 필요: View Audit Log)
        executor = None
        reason = None
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5):
                if entry.target and entry.target.id == user.id:
                    executor = entry.user
                    reason = entry.reason
                    break
        except Exception:
            pass

        by_text = ""
        if executor:
            if executor.id == guild.me.id:
                by_text = _t(guild.id, "log_ban_by_bot")
            else:
                by_text = _t(guild.id, "log_ban_by_mod", mod=str(executor))
        else:
            by_text = _t(guild.id, "log_ban_by_unknown")

        reason_text = reason or _t(guild.id, "log_ban_no_reason")

        emb = discord.Embed(
            title=_t(guild.id, "log_ban_title"),
            color=0xC62828,
            description=(
                f"**User:** {user.mention if hasattr(user,'mention') else user} (`{user}`)\n"
                f"**{_t(guild.id, 'log_ban_by_label')}:** {by_text}\n"
                f"**{_t(guild.id, 'log_ban_reason_label')}:** {reason_text}"
            ),
        )
        avatar = getattr(user, "display_avatar", None) or getattr(user, "avatar", None)
        if avatar:
            emb.set_thumbnail(url=avatar.url)
        await self._send_log(guild, emb)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        executor = None
        reason = None
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=5):
                if entry.target and entry.target.id == user.id:
                    executor = entry.user
                    reason = entry.reason
                    break
        except Exception:
            pass

        by_text = ""
        if executor:
            if executor.id == guild.me.id:
                by_text = _t(guild.id, "log_unban_by_bot")
            else:
                by_text = _t(guild.id, "log_unban_by_mod", mod=str(executor))
        else:
            by_text = _t(guild.id, "log_unban_by_unknown")

        reason_text = reason or _t(guild.id, "log_unban_no_reason")

        emb = discord.Embed(
            title=_t(guild.id, "log_unban_title"),
            color=0x43A047,
            description=(
                f"**User:** {user} (`{user.id}`)\n"
                f"**{_t(guild.id, 'log_unban_by_label')}:** {by_text}\n"
                f"**{_t(guild.id, 'log_unban_reason_label')}:** {reason_text}"
            ),
        )
        await self._send_log(guild, emb)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModLogCog(bot))
