# cogs/security_audit.py
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from utils.db import (
    get_log_channel,
    get_lang,
    get_risk_config,
    get_spam_config,
    get_lockdown_config,
    get_panic_state,
    list_backups,
)
from utils.i18n import t as _t


def _bool_txt(gid: int, b: bool) -> str:
    return _t(gid, "bool_on") if b else _t(gid, "bool_off")


class SecurityAuditCog(commands.Cog):
    """보안 점검 리포트"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="security_audit", description="Run a security audit / 보안 점검 보고서")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def security_audit(self, itx: discord.Interaction):
        gid = itx.guild_id
        g = itx.guild
        await itx.response.defer(ephemeral=True)

        # --- Gather ---
        log_ch_id = get_log_channel(gid)
        lang = get_lang(gid)
        risk = get_risk_config(gid)
        spam = get_spam_config(gid)
        lockdown = get_lockdown_config(gid)
        panic = get_panic_state(gid)
        backups = list_backups(gid, limit=5)

        # Mentions
        log_ch_txt = f"<#{log_ch_id}>" if log_ch_id else _t(gid, "none")
        wl = spam.get("everyone_whitelist", []) or []
        wl_txt = ", ".join(f"<@&{rid}>" for rid in wl) if wl else _t(gid, "none")

        # Latest backup text
        if backups:
            latest = backups[0]["created_at"]
            # created_at은 timezone-aware일 가능성 → 보기 좋게 포맷
            if isinstance(latest, datetime):
                latest_txt = latest.strftime("%Y-%m-%d %H:%M")
            else:
                latest_txt = str(latest)
            backups_txt = _t(gid, "audit_backups_some", count=len(backups), latest=latest_txt)
        else:
            backups_txt = _t(gid, "audit_backups_none")

        # --- Build embed ---
        title = _t(gid, "audit_title")
        emb = discord.Embed(title=title, color=0x2E7D32)

        # Header section
        emb.add_field(
            name=_t(gid, "audit_header"),
            value=(
                f"• {_t(gid, 'audit_log_channel')}: {log_ch_txt}\n"
                f"• {_t(gid, 'audit_language')}: {('한국어' if lang == 'ko' else 'English')}"
            ),
            inline=False,
        )

        # Risk
        emb.add_field(
            name=_t(gid, "audit_section_risk"),
            value=(
                f"- {_t(gid, 'audit_min_account_age')}: {risk['min_account_age_hours']}h\n"
                f"- {_t(gid, 'audit_raid_detection')}: {risk['raid_join_count']} / {risk['raid_join_window_sec']}s"
            ),
            inline=False,
        )

        # Spam
        emb.add_field(
            name=_t(gid, "audit_section_spam"),
            value=(
                f"- {_t(gid, 'audit_rate_limit')}: {spam['max_msgs_per_10s']} / 10s\n"
                f"- {_t(gid, 'audit_mentions_limit')}: {spam['max_mentions_per_msg']} / msg\n"
                f"- {_t(gid, 'audit_block_everyone')}: {_bool_txt(gid, spam['block_everyone_here'])}\n"
                f"- {_t(gid, 'audit_link_filter')}: {_bool_txt(gid, spam['enable_link_filter'])}\n"
                f"- {_t(gid, 'audit_whitelist')}: {wl_txt}"
            ),
            inline=False,
        )

        # Lockdown
        emb.add_field(
            name=_t(gid, "audit_section_lockdown"),
            value=(
                f"- {_t(gid, 'audit_lockdown_enabled')}: {_bool_txt(gid, lockdown['enabled'])}\n"
                f"- {_t(gid, 'audit_lockdown_min_account')}: {lockdown['min_account_age_hours']}h\n"
                f"- {_t(gid, 'audit_lockdown_min_guild')}: {lockdown['min_guild_age_hours']}h"
            ),
            inline=False,
        )

        # Panic
        emb.add_field(
            name=_t(gid, "audit_section_panic"),
            value=f"- {_t(gid, 'audit_panic_status')}: {_bool_txt(gid, panic['enabled'])}",
            inline=False,
        )

        # Backups
        emb.add_field(
            name=_t(gid, "audit_section_backups"),
            value=backups_txt,
            inline=False,
        )

        # Footer with hint
        emb.set_footer(text=_t(gid, "audit_footer_hint"))

        await itx.followup.send(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SecurityAuditCog(bot))
