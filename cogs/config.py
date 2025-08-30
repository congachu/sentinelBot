import discord
from discord import app_commands
from discord.ext import commands

from utils.db import (
    upsert_guild, set_log_channel, get_log_channel,
    set_lang, get_lang
)
from utils.i18n import t

class ConfigCog(commands.Cog):
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
    async def on_guild_join(self, guild: discord.Guild):
        upsert_guild(guild.id)

    # /setlog <channel or 'clear'>
    @app_commands.command(name="setlog", description="Set the log channel / 로그 채널 설정")
    @app_commands.describe(channel="보안 로그를 보낼 채널(비우면 해제)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlog(self, itx: discord.Interaction, channel: discord.TextChannel | None = None):
        upsert_guild(itx.guild_id)
        if channel is None:
            set_log_channel(itx.guild_id, None)
            await itx.response.send_message(
                t(itx.guild_id, "setlog_clear"), ephemeral=True
            )
            return

        set_log_channel(itx.guild_id, channel.id)
        await itx.response.send_message(
            t(itx.guild_id, "setlog_ok", channel=channel.mention), ephemeral=True
        )

    # /showconfig
    @app_commands.command(name="showconfig", description="Show current config / 현재 설정 보기")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def showconfig(self, itx: discord.Interaction):
        ch_id = get_log_channel(itx.guild_id)
        channel_disp = itx.guild.get_channel(ch_id).mention if ch_id else "미설정 / Not set"
        lang = get_lang(itx.guild_id)
        await itx.response.send_message(
            t(itx.guild_id, "showconfig", channel=channel_disp, lang=lang),
            ephemeral=True
        )

    # /testlog
    @app_commands.command(name="testlog", description="Send a test log / 로그 테스트 전송")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def testlog(self, itx: discord.Interaction):
        emb = discord.Embed(
            title=t(itx.guild_id, "testlog_title"),
            description=t(itx.guild_id, "testlog_body"),
            color=0xE53935
        )
        ok = await self._send_log(itx.guild, emb)
        if ok:
            await itx.response.send_message("✅ OK", ephemeral=True)
        else:
            await itx.response.send_message(t(itx.guild_id, "not_set"), ephemeral=True)

    # /setlang <ko|en>
    @app_commands.command(name="setlang", description="Set bot language / 봇 언어 설정")
    @app_commands.describe(lang="ko 또는 en")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlang(self, itx: discord.Interaction, lang: str):
        lang = lang.lower().strip()
        if lang not in ("ko", "en"):
            lang = "ko"
        set_lang(itx.guild_id, lang)
        await itx.response.send_message(
            t(itx.guild_id, "setlang_ok", lang=lang), ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
