# cogs/help.py
import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import t as _t

# SentinelBot에서 제공하는 주요 명령을 카테고리로 정리
CATEGORIES = {
    "basic": [
        ("setlog", "Slash"),
        ("showconfig", "Slash"),
        ("testlog", "Slash"),
        ("setlang", "Slash"),
    ],
    "policies": [
        ("policies", "Slash"),
        ("riskset", "Slash"),
        ("spamset", "Slash"),
        ("lockdownset", "Slash"),
    ],
    "admin": [
        ("lockdown", "Slash"),
        ("panic", "Slash"),
        ("unpanic", "Slash"),
    ],
    "backup": [
        ("backup_create", "Slash"),
        ("backup_list", "Slash"),
        ("backup_delete", "Slash"),
        ("backup_restore", "Slash"),
    ],
}

def _command_lookup(bot: commands.Bot) -> dict[str, app_commands.Command]:
    table: dict[str, app_commands.Command] = {}
    for cmd in bot.tree.get_commands():
        table[cmd.name] = cmd
        # 그룹 커맨드 처리(있을 경우)
        if isinstance(cmd, app_commands.Group):
            for sub in cmd.commands:
                table[sub.name] = sub
    return table

class HelpCog(commands.Cog):
    """한/영 도움말"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show help / 도움말 보기")
    @app_commands.describe(command="명령어 이름(선택) / Command name (optional)")
    async def help_cmd(self, itx: discord.Interaction, command: str | None = None):
        guild_id = itx.guild_id or 0
        await itx.response.defer(ephemeral=True, thinking=False)

        # 특정 명령 상세
        if command:
            table = _command_lookup(self.bot)
            cmd = table.get(command.lower())
            if not cmd:
                await itx.followup.send(_t(guild_id, "help_unknown_command", name=command), ephemeral=True)
                return

            # 간단한 상세 정보 (설명 + 사용법 표기)
            title = _t(guild_id, "help_command_title", name=f"/{cmd.name}")
            desc_lines = [
                _t(guild_id, "help_command_desc"),
                f"> {cmd.description or '-'}",
            ]

            # 파라미터 표시
            if getattr(cmd, "parameters", None):
                desc_lines.append(_t(guild_id, "help_command_usage"))
                for p in cmd.parameters:
                    opt = "optional" if p.default is not app_commands._missing.MISSING else "required"
                    # 한/영 변환
                    opt_txt = _t(guild_id, "help_optional") if opt == "optional" else _t(guild_id, "help_required")
                    desc_lines.append(f"- `{p.name}` ({opt_txt}) — {p.description or '-'}")

            # 예시 안내(간단)
            desc_lines.append("")
            desc_lines.append(_t(guild_id, "help_examples_header"))
            # 대표 예시 몇 개
            examples = {
                "setlog": "/setlog #security-log",
                "setlang": "/setlang ko",
                "riskset": "/riskset min_account_age_hours:72 raid_join_window_sec:30 raid_join_count:5",
                "spamset": "/spamset max_msgs_per_10s:8 max_mentions_per_msg:5 block_everyone_here:true",
                "lockdownset": "/lockdownset min_account_age_hours:72 min_guild_age_hours:24",
                "lockdown": "/lockdown true",
                "panic": "/panic",
                "unpanic": "/unpanic",
                "backup_create": "/backup_create label:baseline",
                "backup_restore": "/backup_restore 12",
            }
            sample = examples.get(cmd.name)
            if sample:
                desc_lines.append(f"• `{sample}`")

            # 정책 반영 지연 안내(해당되는 명령에만)
            if cmd.name in {"riskset", "spamset", "lockdownset"}:
                desc_lines.append("")
                desc_lines.append(_t(guild_id, "policy_update_delay"))

            emb = discord.Embed(title=title, description="\n".join(desc_lines), color=0x5865F2)
            emb.set_footer(text=_t(guild_id, "help_footer"))
            await itx.followup.send(embed=emb, ephemeral=True)
            return

        # 전체 목록
        title = _t(guild_id, "help_title")
        intro = _t(guild_id, "help_intro")

        emb = discord.Embed(title=title, description=intro, color=0x5865F2)

        # 카테고리별 섹션
        labels = {
            "basic": _t(guild_id, "help_cat_basic"),
            "policies": _t(guild_id, "help_cat_policies"),
            "admin": _t(guild_id, "help_cat_admin"),
            "backup": _t(guild_id, "help_cat_backup"),
        }

        # 실제 등록된 명령만 뽑아 표시
        table = _command_lookup(self.bot)
        for key, items in CATEGORIES.items():
            present = []
            for name, _kind in items:
                if name in table:
                    present.append(f"`/{name}` — {table[name].description or '-'}")
            if present:
                emb.add_field(name=labels[key], value="\n".join(present), inline=False)

        emb.add_field(
            name=_t(guild_id, "help_tips_title"),
            value=_t(guild_id, "help_tips_body"),
            inline=False,
        )
        emb.set_footer(text=_t(guild_id, "help_footer"))

        await itx.followup.send(embed=emb, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
