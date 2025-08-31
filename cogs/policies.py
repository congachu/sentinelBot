# cogs/policies.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
from utils.db import (
    upsert_guild,
    get_risk_config, set_risk_config,
    get_spam_config, set_spam_config,
    get_lockdown_config,
    add_spam_whitelist_role, remove_spam_whitelist_role
)
from utils.i18n import t as _t


class PoliciesCog(commands.Cog):
    """길드별 Risk/Spam/Lockdown 정책 조회/설정 + 화이트리스트"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="policies", description="Show current policies / 현재 정책 보기")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def policies(self, itx: discord.Interaction):
        upsert_guild(itx.guild_id)
        r = get_risk_config(itx.guild_id)
        s = get_spam_config(itx.guild_id)
        l = get_lockdown_config(itx.guild_id)

        wl = s.get("everyone_whitelist", [])
        wl_txt = ", ".join(f"<@&{rid}>" for rid in wl) if wl else _t(itx.guild_id, "none")

        body = _t(
            itx.guild_id,
            "policies_body",
            min_age=r["min_account_age_hours"],
            raid_count=r["raid_join_count"],
            raid_win=r["raid_join_window_sec"],
            max_msgs=s["max_msgs_per_10s"],
            max_mentions=s["max_mentions_per_msg"],
            block_eh=_t(itx.guild_id, "bool_on") if s["block_everyone_here"] else _t(itx.guild_id, "bool_off"),
            link_filter=_t(itx.guild_id, "bool_on") if s["enable_link_filter"] else _t(itx.guild_id, "bool_off"),
        )
        body += (
            f"\n- Whitelist: {wl_txt}"
            f"\n\n{_t(itx.guild_id, 'lockdown_title')}\n"
            f"- {_t(itx.guild_id, 'lockdown_enabled', state=_t(itx.guild_id, 'bool_on') if l['enabled'] else _t(itx.guild_id, 'bool_off'))}\n"
            f"- {_t(itx.guild_id, 'lockdown_min_age', hours=l['min_account_age_hours'])}\n"
            f"- {_t(itx.guild_id, 'lockdown_min_guild_age', hours=l['min_guild_age_hours'])}"
        )
        body += (
            f"\n\n**{_t(itx.guild_id, 'auto_enforce_title')}**\n"
            f"- {_t(itx.guild_id, 'auto_enforce_rule_rate_link')}\n"
            f"- {_t(itx.guild_id, 'auto_enforce_rule_everyone')}\n"
            f"- {_t(itx.guild_id, 'auto_enforce_rule_join')}"
        )

        emb = discord.Embed(title=_t(itx.guild_id, "policies_title"), description=body, color=0x546E7A)
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
        self.bot.dispatch("risk_config_updated", itx.guild_id)

        r = get_risk_config(itx.guild_id)
        desc = (
            f"{_t(itx.guild_id, 'riskset_ok')}\n"
            f"- Min account age: {r['min_account_age_hours']}h\n"
            f"- Raid detection: {r['raid_join_count']} users/{r['raid_join_window_sec']}s\n\n"
            f"{_t(itx.guild_id, 'policy_update_delay')}"
        )
        emb = discord.Embed(title="🔧 Risk Policy", description=desc, color=0x455A64)
        await itx.response.send_message(embed=emb, ephemeral=True)

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
        self.bot.dispatch("spam_config_updated", itx.guild_id)

        s = get_spam_config(itx.guild_id)
        wl = s.get("everyone_whitelist", [])
        wl_txt = ", ".join(f"<@&{rid}>" for rid in wl) if wl else _t(itx.guild_id, "none")

        desc = (
            f"{_t(itx.guild_id, 'spamset_ok')}\n"
            f"- Max msgs/10s: {s['max_msgs_per_10s']}\n"
            f"- Max mentions/msg: {s['max_mentions_per_msg']}\n"
            f"- Block @everyone/@here: {'ON' if s['block_everyone_here'] else 'OFF'}\n"
            f"- Link filter: {'ON' if s['enable_link_filter'] else 'OFF'}\n"
            f"- Whitelist: {wl_txt}\n\n"
            f"{_t(itx.guild_id, 'policy_update_delay')}"
        )
        emb = discord.Embed(title="🛡️ Spam Policy", description=desc, color=0x455A64)
        await itx.response.send_message(embed=emb, ephemeral=True)

    # ========= everyone/here 화이트리스트 =========
    @app_commands.command(name="spamallow", description="Manage @everyone/@here whitelist / 화이트리스트 관리")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def spamallow(self, itx: discord.Interaction, action: Literal["add", "remove", "list"], role: discord.Role | None = None):
        action = action.lower()
        if action == "add" and role:
            add_spam_whitelist_role(itx.guild_id, role.id)
            self.bot.dispatch("spam_config_updated", itx.guild_id)
            msg = _t(itx.guild_id, "spamallow_added", role=role.mention)
        elif action == "remove" and role:
            remove_spam_whitelist_role(itx.guild_id, role.id)
            self.bot.dispatch("spam_config_updated", itx.guild_id)
            msg = _t(itx.guild_id, "spamallow_removed", role=role.mention)
        elif action == "list":
            s = get_spam_config(itx.guild_id)
            wl = s.get("everyone_whitelist", [])
            wl_txt = ", ".join(f"<@&{rid}>" for rid in wl) if wl else _t(itx.guild_id, "none")
            msg = _t(itx.guild_id, "spamallow_list", roles=wl_txt)
        else:
            msg = _t(itx.guild_id, "spamallow_hint")

        emb = discord.Embed(title="📝 Whitelist", description=msg, color=0x455A64)
        await itx.response.send_message(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PoliciesCog(bot))
