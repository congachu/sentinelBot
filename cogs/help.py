# cogs/help.py
import discord
from discord import app_commands
from discord.ext import commands

from utils.i18n import t as _t

# SentinelBot에서 제공하는 주요 명령을 카테고리로 정리
# kind: "Slash" = 일반 슬래시, "Group" = 그룹 명령(하위 커맨드 존재)
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
        ("spamallow", "Group"),  # ✅ 화이트리스트 그룹 명령 추가
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
    """
    슬래시 명령을 조회하기 쉽게 평탄화한다.
    - 단일 명령: "name"
    - 그룹 명령: "group", 그리고 하위는 "group sub" 키로 접근 가능
    """
    table: dict[str, app_commands.Command] = {}
    for cmd in bot.tree.get_commands():
        table[cmd.name] = cmd
        if isinstance(cmd, app_commands.Group):
            # 그룹 자체도 키로 등록
            for sub in cmd.commands:
                table[f"{cmd.name} {sub.name}"] = sub  # 예: "spamallow add"
    return table


class HelpCog(commands.Cog):
    """한/영 도움말"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show help / 도움말 보기")
    @app_commands.describe(command="명령어 이름(선택). 예) spamallow add / Command name (optional). e.g., spamallow add")
    async def help_cmd(self, itx: discord.Interaction, command: str | None = None):
        guild_id = itx.guild_id or 0
        await itx.response.defer(ephemeral=True, thinking=False)

        # 특정 명령 상세
        if command:
            table = _command_lookup(self.bot)
            key = command.strip().lower()
            cmd = table.get(key)
            if not cmd:
                # 단일 이름만 들어온 경우 다시 한 번 시도
                cmd = table.get(key.split()[0]) if " " in key else None
                if not cmd:
                    await itx.followup.send(_t(guild_id, "help_unknown_command", name=command), ephemeral=True)
                    return

            # 표시용 이름: 공백 포함 입력이면 그대로, 아니면 /cmd.name
            display_name = f"/{key}" if " " in key else f"/{cmd.name}"
            title = _t(guild_id, "help_command_title", name=display_name)
            desc_lines = [
                _t(guild_id, "help_command_desc"),
                f"> {cmd.description or '-'}",
            ]

            # 파라미터 표시
            if getattr(cmd, "parameters", None):
                desc_lines.append(_t(guild_id, "help_command_usage"))
                for p in cmd.parameters:
                    # discord.py 내부 MISSING 비교 안전 처리
                    required = getattr(p, "required", False)
                    opt_txt = _t(guild_id, "help_required") if required else _t(guild_id, "help_optional")
                    desc_lines.append(f"- `{p.name}` ({opt_txt}) — {p.description or '-'}")

            # 예시 안내
            desc_lines.append("")
            desc_lines.append(_t(guild_id, "help_examples_header"))
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
                # ✅ 그룹 예시
                "spamallow": "/spamallow add @Trusted\n/spamallow remove @Trusted\n/spamallow list",
                "spamallow add": "/spamallow add @Trusted",
                "spamallow remove": "/spamallow remove @Trusted",
                "spamallow list": "/spamallow list",
            }
            sample = examples.get(key) or examples.get(cmd.name)
            if sample:
                # 여러 줄 예시는 그대로 표시
                for line in str(sample).splitlines():
                    desc_lines.append(f"• `{line}`")

            # 정책 반영 지연 안내(해당되는 명령에만)
            if (key.split()[0] if " " in key else cmd.name) in {"riskset", "spamset", "lockdownset"}:
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
            for name, kind in items:
                if name not in table:
                    continue
                if kind == "Group":
                    # 그룹은 add|remove|list 를 안내에 함께 표시
                    present.append(f"`/{name} add|remove|list` — {table[name].description or '-'}")
                else:
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
