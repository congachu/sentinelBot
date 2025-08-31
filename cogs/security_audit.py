# cogs/security_audit.py
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import (
    get_log_channel, get_lang,
    get_risk_config, get_spam_config,
    get_lockdown_config, get_panic_state,
    list_backups,
)
from utils.i18n import t as _t


class SecurityAuditCog(commands.Cog):
    """서버 보안 설정 점검 + 보안 점수 산출"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="security_audit", description="Security audit with a score / 보안 점검(점수 포함)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def security_audit(self, itx: discord.Interaction):
        gid = itx.guild_id
        assert gid is not None

        await itx.response.defer(ephemeral=True, thinking=True)

        # ---- Load configs
        log_ch = get_log_channel(gid)
        lang = get_lang(gid)
        risk = get_risk_config(gid)
        spam = get_spam_config(gid)
        lockdown = get_lockdown_config(gid)
        panic = get_panic_state(gid)
        backups = list_backups(gid, limit=1)

        # ---- Score calc (0~100)
        score = 0
        details: list[str] = []

        # Emojis
        OK = "✅"
        WARN = "⚠️"
        BAD = "❌"

        # 1) Log channel (15)
        if log_ch:
            score += 15
            details.append(f"{OK} " + _t(gid, "audit_line_log_set"))
        else:
            details.append(f"{BAD} " + _t(gid, "audit_line_log_missing"))

        # 2) Language sanity (5)
        if lang in ("ko", "en"):
            score += 5
            # 굳이 라인 출력은 생략

        # 3) Risk (20)
        #   - min account age >= 72h → 10
        #   - raid detection (count >=3 AND window <= 60s) → 10
        if int(risk.get("min_account_age_hours", 0)) >= 72:
            score += 10
            details.append(f"{OK} " + _t(gid, "audit_line_age_ok"))
        else:
            details.append(f"{WARN} " + _t(gid, "audit_line_age_low", hours=risk.get("min_account_age_hours", 0)))

        if int(risk.get("raid_join_count", 0)) >= 3 and int(risk.get("raid_join_window_sec", 9999)) <= 60:
            score += 10
            details.append(f"{OK} " + _t(gid, "audit_line_raid_ok"))
        else:
            details.append(
                f"{WARN} "
                + _t(
                    gid,
                    "audit_line_raid_weak",
                    count=risk.get("raid_join_count", 0),
                    sec=risk.get("raid_join_window_sec", 0),
                )
            )

        # 4) Spam (35)
        #   - rate limit <=10 → 10
        #   - mentions limit <=10 → 10
        #   - block everyone/here ON → 10
        #   - link filter ON → 5
        rate = int(spam.get("max_msgs_per_10s", 999))
        if rate <= 10:
            score += 10
            details.append(f"{OK} " + _t(gid, "audit_line_rate_ok", limit=rate))
        else:
            details.append(f"{WARN} " + _t(gid, "audit_line_rate_bad", limit=rate))

        mentions_lim = int(spam.get("max_mentions_per_msg", 999))
        if mentions_lim <= 10:
            score += 10
            details.append(f"{OK} " + _t(gid, "audit_line_mentions_ok", limit=mentions_lim))
        else:
            details.append(f"{WARN} " + _t(gid, "audit_line_mentions_bad", limit=mentions_lim))

        if bool(spam.get("block_everyone_here", False)):
            score += 10
            details.append(f"{OK} " + _t(gid, "audit_line_block_everyone_on"))
        else:
            details.append(f"{BAD} " + _t(gid, "audit_line_block_everyone_off"))

        if bool(spam.get("enable_link_filter", False)):
            score += 5
            details.append(f"{OK} " + _t(gid, "audit_line_link_on"))
        else:
            details.append(f"{WARN} " + _t(gid, "audit_line_link_off"))

        # 5) Lockdown (10) — 켜져 있으면 +10 (평시 OFF는 감점 없음, 정보 라인만)
        if bool(lockdown.get("enabled", False)):
            score += 10
            details.append(f"{OK} " + _t(gid, "audit_line_lockdown_on"))
        else:
            details.append(f"{WARN} " + _t(gid, "audit_line_lockdown_off_note"))

        # 6) Backups exist (5)
        if backups:
            score += 5
            details.append(f"{OK} " + _t(gid, "audit_line_backups_some"))
        else:
            details.append(f"{WARN} " + _t(gid, "audit_line_backups_none"))

        # 7) Panic OFF (5)
        if not bool(panic.get("enabled", False)):
            score += 5
            details.append(f"{OK} " + _t(gid, "audit_line_panic_off"))
        else:
            details.append(f"{WARN} " + _t(gid, "audit_line_panic_on"))

        # ---- Build embed
        title = _t(gid, "audit_title")
        emb = discord.Embed(title=title, color=0x546E7A)

        emb.add_field(
            name=_t(gid, "audit_score_title"),
            value=_t(gid, "audit_score_line", score=score),
            inline=False,
        )

        # 한 번에 보기 쉽게 본문 묶기
        emb.add_field(
            name=_t(gid, "audit_header"),
            value="\n".join(details),
            inline=False,
        )
        emb.set_footer(text=_t(gid, "audit_footer_hint"))

        await itx.followup.send(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SecurityAuditCog(bot))
