# cogs/backup.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import save_backup, list_backups, get_backup, delete_backup
from utils.i18n import t as _t

# =========================
# Helper: permissions / overwrites / serialize
# =========================

def _perm_to_int(perms: discord.Permissions) -> int:
    return perms.value

def _int_to_perm(val: int) -> discord.Permissions:
    return discord.Permissions(val)

def _serialize_overwrites(ow_map: Dict) -> List[dict]:
    """
    Overwrites -> [{target_id, target_type, allow, deny}]
    target_type: role|member
    """
    out = []
    for target, ow in ow_map.items():
        allow, deny = ow.pair()
        out.append({
            "target_id": int(target.id),
            "target_type": "role" if isinstance(target, discord.Role) else "member",
            "allow": allow.value,
            "deny": deny.value,
        })
    return out

def _make_overwrites(guild: discord.Guild, items: List[dict]) -> Dict:
    """
    [{target_id, target_type, allow, deny}] -> Overwrites dict
    존재하지 않는 타겟은 건너뜀(복구 비파괴)
    """
    result = {}
    for item in items:
        target = None
        if item["target_type"] == "role":
            target = guild.get_role(int(item["target_id"]))
        else:
            target = guild.get_member(int(item["target_id"]))
        if not target:
            continue
        allow = _int_to_perm(item["allow"])
        deny = _int_to_perm(item["deny"])
        result[target] = discord.PermissionOverwrite.from_pair(allow, deny)
    return result

def _serialize_roles(guild: discord.Guild) -> List[dict]:
    roles = []
    # position 오름차순(최하단->최상단)로 저장해두고, 복구 시 그대로 정렬에 사용
    for r in sorted(guild.roles, key=lambda x: x.position):
        roles.append({
            "id": int(r.id),
            "name": r.name,
            "color": r.color.value,
            "hoist": r.hoist,
            "mentionable": r.mentionable,
            "permissions": _perm_to_int(r.permissions),
            "position": r.position,
            "is_everyone": r.is_default(),
        })
    return roles

def _serialize_channels(guild: discord.Guild) -> dict:
    cats, texts, voices = [], [], []
    # position 기준 정렬
    for ch in sorted(guild.channels, key=lambda c: getattr(c, "position", 0)):
        common = {
            "id": int(ch.id),
            "name": ch.name,
            "position": getattr(ch, "position", 0),
            "overwrites": _serialize_overwrites(ch.overwrites),
            "parent_id": ch.category_id if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)) else None,
        }
        if isinstance(ch, discord.CategoryChannel):
            cats.append(common)
        elif isinstance(ch, discord.TextChannel):
            texts.append({
                **common,
                "topic": ch.topic,
                "nsfw": ch.nsfw,
                "slowmode_delay": ch.slowmode_delay,
                "type": "text",
            })
        elif isinstance(ch, discord.VoiceChannel):
            voices.append({
                **common,
                "user_limit": ch.user_limit,
                "bitrate": ch.bitrate,
                "type": "voice",
            })
        # 필요 시 Forum/Stage 등은 확장 가능
    return {"categories": cats, "texts": texts, "voices": voices}

# =========================
# Diff helpers (변경된 필드만 PATCH)
# =========================
def _norm(v):
    return "" if v is None else v

def _overwrites_equal(a: dict, b_items: list[dict]) -> bool:
    """채널 overwrites 간단 동등성 비교: (타깃, allow, deny) 셋 일치 여부"""
    def pack(map_):
        out = []
        for target, ow in map_.items():
            allow, deny = ow.pair()
            out.append((getattr(target, "id", None), "role" if isinstance(target, discord.Role) else "member",
                        allow.value, deny.value))
        return set(out)

    def pack_items(items):
        return set((int(i["target_id"]), i["target_type"], int(i["allow"]), int(i["deny"])) for i in items)

    try:
        return pack(a) == pack_items(b_items)
    except Exception:
        return False

def _diff_role_fields(role: discord.Role, snap: dict) -> dict:
    fields = {}
    if role.name != snap["name"]:
        fields["name"] = snap["name"]
    if role.colour.value != int(snap["color"]):
        fields["colour"] = discord.Colour(int(snap["color"]))
    if bool(role.hoist) != bool(snap["hoist"]):
        fields["hoist"] = bool(snap["hoist"])
    if bool(role.mentionable) != bool(snap["mentionable"]):
        fields["mentionable"] = bool(snap["mentionable"])
    if role.permissions.value != int(snap["permissions"]):
        fields["permissions"] = discord.Permissions(int(snap["permissions"]))
    return fields

def _diff_category_fields(cat: discord.CategoryChannel, snap: dict, ows: dict) -> dict:
    fields = {}
    if cat.name != snap["name"]:
        fields["name"] = snap["name"]
    if cat.position != int(snap["position"]):
        fields["position"] = int(snap["position"])
    if not _overwrites_equal(cat.overwrites, snap["overwrites"]):
        fields["overwrites"] = ows
    return fields

def _diff_text_fields(ch: discord.TextChannel, snap: dict, parent: discord.CategoryChannel | None, ows: dict) -> dict:
    fields = {}
    if ch.name != snap["name"]:
        fields["name"] = snap["name"]
    if _norm(ch.topic) != _norm(snap["topic"]):
        fields["topic"] = snap["topic"]
    if bool(ch.nsfw) != bool(snap["nsfw"]):
        fields["nsfw"] = bool(snap["nsfw"])
    if int(ch.slowmode_delay or 0) != int(snap["slowmode_delay"] or 0):
        fields["slowmode_delay"] = int(snap["slowmode_delay"] or 0)
    if (ch.category_id or None) != (parent.id if parent else None):
        fields["category"] = parent
    if ch.position != int(snap["position"]):
        fields["position"] = int(snap["position"])
    if not _overwrites_equal(ch.overwrites, snap["overwrites"]):
        fields["overwrites"] = ows
    return fields

def _diff_voice_fields(ch: discord.VoiceChannel, snap: dict, parent: discord.CategoryChannel | None, ows: dict) -> dict:
    fields = {}
    if ch.name != snap["name"]:
        fields["name"] = snap["name"]
    if int(ch.bitrate or 64000) != int(snap["bitrate"] or 64000):
        fields["bitrate"] = int(snap["bitrate"] or 64000)
    if int(ch.user_limit or 0) != int(snap["user_limit"] or 0):
        fields["user_limit"] = int(snap["user_limit"] or 0)
    if (ch.category_id or None) != (parent.id if parent else None):
        fields["category"] = parent
    if ch.position != int(snap["position"]):
        fields["position"] = int(snap["position"])
    if not _overwrites_equal(ch.overwrites, snap["overwrites"]):
        fields["overwrites"] = ows
    return fields

# =========================
# Throttler (서버/레이트리밋 보호)
# =========================
THROTTLE_CONCURRENCY = 1
WRITE_DELAY = 0.7
_sem = asyncio.Semaphore(THROTTLE_CONCURRENCY)

async def throttled(coro):
    async with _sem:
        try:
            return await coro
        finally:
            await asyncio.sleep(WRITE_DELAY)

# =========================
# Cog
# =========================
class BackupCog(commands.Cog):
    """서버 역할/카테고리/채널/권한 백업 & 복구 (비파괴)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- Create ----------
    @app_commands.command(name="backup_create", description="Create server backup / 서버 전체 백업 생성")
    @app_commands.describe(label="선택사항: 백업 라벨")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_create(self, itx: discord.Interaction, label: str | None = None):
        await itx.response.defer(ephemeral=True, thinking=True)

        g = itx.guild
        payload = {
            "guild": {"id": int(g.id), "name": g.name},
            "roles": _serialize_roles(g),
            "channels": _serialize_channels(g),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        bid = save_backup(g.id, label, payload)
        await itx.followup.send(_t(g.id, "backup_done", id=bid))

    # ---------- List ----------
    @app_commands.command(name="backup_list", description="List backups / 백업 목록")
    @app_commands.describe(limit="표시 개수 (1~25)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def backup_list(self, itx: discord.Interaction, limit: app_commands.Range[int, 1, 25] = 10):
        rows = list_backups(itx.guild_id, limit=limit)
        if not rows:
            await itx.response.send_message(_t(itx.guild_id, "backup_list_empty"), ephemeral=True)
            return
        lines = [_t(itx.guild_id, "backup_list_title")]
        for r in rows:
            created = r["created_at"].strftime("%Y-%m-%d %H:%M")
            lbl = r["label"] or "-"
            lines.append(_t(itx.guild_id, "backup_item", id=r["id"], created=created, label=lbl))
        await itx.response.send_message("\n".join(lines), ephemeral=True)

    # ---------- Delete ----------
    @app_commands.command(name="backup_delete", description="Delete backup / 백업 삭제")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_delete(self, itx: discord.Interaction, backup_id: int):
        ok = delete_backup(itx.guild_id, backup_id)
        if not ok:
            await itx.response.send_message(_t(itx.guild_id, "backup_not_found", id=backup_id), ephemeral=True)
            return
        await itx.response.send_message(_t(itx.guild_id, "delete_ok", id=backup_id), ephemeral=True)

    # ---------- Restore ----------
    @app_commands.command(name="backup_restore", description="Restore backup (non-destructive) / 백업 복구(비파괴)")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_restore(self, itx: discord.Interaction, backup_id: int):
        await itx.response.defer(ephemeral=True, thinking=True)

        g = itx.guild
        data = get_backup(g.id, backup_id)
        if not data:
            await itx.followup.send(_t(g.id, "backup_not_found", id=backup_id))
            return

        failed_any = False

        # ===== 1) Roles =====
        try:
            snapshot_roles = data["roles"]
            role_map: Dict[int, discord.Role] = {}  # old_id -> role_obj

            existing_by_id = {r.id: r for r in g.roles}
            for r in snapshot_roles:
                if r["is_everyone"]:
                    # @everyone 권한만 비교/동기화
                    everyone = g.default_role
                    if everyone.permissions.value != int(r["permissions"]):
                        await throttled(everyone.edit(
                            permissions=discord.Permissions(int(r["permissions"])),
                            reason="Restore snapshot (@everyone perms)",
                        ))
                    role_map[int(r["id"])] = everyone
                    continue

                exist = existing_by_id.get(int(r["id"]))
                if exist:
                    fields = _diff_role_fields(exist, r)
                    if fields:
                        await throttled(exist.edit(**fields, reason="Restore snapshot (update role)"))
                    role_map[int(r["id"])] = exist
                else:
                    new_role = await throttled(g.create_role(
                        name=r["name"],
                        colour=discord.Colour(int(r["color"])),
                        hoist=bool(r["hoist"]),
                        mentionable=bool(r["mentionable"]),
                        permissions=discord.Permissions(int(r["permissions"])),
                        reason="Restore snapshot (create role)",
                    ))
                    role_map[int(r["id"])] = new_role

            # 포지션은 변경 필요한 것만 묶어서
            desired_positions = []
            for r in sorted(snapshot_roles, key=lambda x: x["position"]):
                role = role_map.get(int(r["id"]))
                if role and not role.is_default() and role.position != int(r["position"]):
                    desired_positions.append({"role": role, "position": int(r["position"])})
            if desired_positions:
                await throttled(g.edit_role_positions(positions=desired_positions))
        except Exception:
            failed_any = True

        # ===== 2) Categories =====
        try:
            snap = data["channels"]
            cat_map: Dict[int, discord.CategoryChannel] = {}
            existing_cats_by_id = {c.id: c for c in g.categories}

            for c in snap["categories"]:
                old_id = int(c["id"])
                exist = existing_cats_by_id.get(old_id)
                ows = _make_overwrites(g, c["overwrites"])

                if exist:
                    fields = _diff_category_fields(exist, c, ows)
                    if fields:
                        await throttled(exist.edit(**fields, reason="Restore snapshot (update category)"))
                    cat_map[old_id] = exist
                else:
                    new_cat = await throttled(g.create_category(
                        name=c["name"],
                        overwrites=ows,
                        reason="Restore snapshot (create category)",
                    ))
                    if new_cat.position != int(c["position"]):
                        await throttled(new_cat.edit(position=int(c["position"])))
                    cat_map[old_id] = new_cat
        except Exception:
            failed_any = True

        # ===== 3) Text Channels =====
        try:
            existing_text_by_id = {ch.id: ch for ch in g.text_channels}
            for t in snap["texts"]:
                old_id = int(t["id"])
                parent = cat_map.get(int(t["parent_id"])) if t["parent_id"] else None
                ows = _make_overwrites(g, t["overwrites"])

                exist = existing_text_by_id.get(old_id)
                if exist:
                    fields = _diff_text_fields(exist, t, parent, ows)
                    if fields:
                        await throttled(exist.edit(**fields, reason="Restore snapshot (update text)"))
                else:
                    new_ch = await throttled(g.create_text_channel(
                        name=t["name"],
                        overwrites=ows,
                        category=parent,
                        reason="Restore snapshot (create text)",
                    ))
                    post_fields = _diff_text_fields(new_ch, t, parent, ows)
                    if post_fields:
                        await throttled(new_ch.edit(**post_fields))
        except Exception:
            failed_any = True

        # ===== 4) Voice Channels =====
        try:
            existing_voice_by_id = {ch.id: ch for ch in g.voice_channels}
            for v in snap["voices"]:
                old_id = int(v["id"])
                parent = cat_map.get(int(v["parent_id"])) if v["parent_id"] else None
                ows = _make_overwrites(g, v["overwrites"])

                exist = existing_voice_by_id.get(old_id)
                if exist:
                    fields = _diff_voice_fields(exist, v, parent, ows)
                    if fields:
                        await throttled(exist.edit(**fields, reason="Restore snapshot (update voice)"))
                else:
                    new_vc = await throttled(g.create_voice_channel(
                        name=v["name"],
                        overwrites=ows,
                        category=parent,
                        reason="Restore snapshot (create voice)",
                    ))
                    post_fields = _diff_voice_fields(new_vc, v, parent, ows)
                    if post_fields:
                        await throttled(new_vc.edit(**post_fields))
        except Exception:
            failed_any = True

        await itx.followup.send(_t(g.id, "restore_done") if not failed_any else _t(g.id, "restore_warn"))

async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
