# cogs/spam_watch.py
import re
import time
import discord
from discord.ext import commands

from utils.db import get_log_channel, get_spam_config
from utils.i18n import t

LINK_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

# 길드별 유저 메시지 타임스탬프 버퍼
_msg_buffer: dict[int, dict[int, list[float]]] = {}  # {guild_id: {user_id: [ts,...]}}

class SpamWatchCog(commands.Cog):
    """스팸·멘션 폭탄·홍보/피싱 링크를 감지하고 제어합니다."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- 내부 헬퍼 ----------
    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> bool:
        ch_id = get_log_channel(guild.id)
        if not ch_id:
            return False
        ch = guild.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
        if ch:
            await ch.send(embed=embed)
            return True
        return False

    async def _delete_and_log(self, message: discord.Message, reason_key: str, **fmt):
        # 메시지 삭제
        try:
            await message.delete()
        except Exception:
            pass

        emb = discord.Embed(
            title=t(message.guild.id, "log_spam_title"),
            color=0xE53935,
            description=(
                f"**User:** {message.author.mention} (`{message.author}`)\n"
                f"**Channel:** {message.channel.mention}\n"
                f"**Reason:** {t(message.guild.id, reason_key, **fmt)}"
            ),
        )
        if message.author.display_avatar:
            emb.set_thumbnail(url=message.author.display_avatar.url)
        emb.set_footer(text=t(message.guild.id, "log_spam_footer_config"))
        await self._send_log(message.guild, emb)

        # 유저 DM 안내
        try:
            await message.author.send(t(message.guild.id, "dm_spam_notice"))
        except Exception:
            pass

    # ---------- 이벤트 훅 ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 봇/DM/시스템/길드없는 메시지 제외
        if not message.guild or message.author.bot:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        now = time.time()

        # 길드별 스팸 정책 로드
        s = get_spam_config(guild_id)
        MAX_MSGS_PER_10S = int(s["max_msgs_per_10s"])
        MAX_MENTIONS_PER_MSG = int(s["max_mentions_per_msg"])
        BLOCK_EVERYONE_HERE = bool(s["block_everyone_here"])
        ENABLE_LINK_FILTER = bool(s["enable_link_filter"])

        # 1) 속도 제한(10초 윈도우)
        gb = _msg_buffer.setdefault(guild_id, {})
        ub = gb.setdefault(user_id, [])
        ub.append(now)
        _msg_buffer[guild_id][user_id] = [t_ for t_ in ub if now - t_ <= 10]

        if len(_msg_buffer[guild_id][user_id]) > MAX_MSGS_PER_10S:
            await self._delete_and_log(
                message,
                "log_spam_reason_rate",
                count=len(_msg_buffer[guild_id][user_id]),
            )
            return

        # 2) @everyone / @here 차단
        if BLOCK_EVERYONE_HERE and message.mention_everyone:
            await self._delete_and_log(message, "log_spam_reason_everyone")
            return

        # 3) 멘션 폭탄(@user / @role 합산)
        total_mentions = len(message.mentions) + len(message.role_mentions)
        if total_mentions > MAX_MENTIONS_PER_MSG:
            await self._delete_and_log(
                message,
                "log_spam_reason_mentions",
                mentions=total_mentions,
                limit=MAX_MENTIONS_PER_MSG,
            )
            return

        # 4) 링크 필터(옵션) — message_content intent 필요
        if ENABLE_LINK_FILTER:
            content = getattr(message, "content", None)
            if isinstance(content, str) and content:
                urls = LINK_RE.findall(content)
                if urls:
                    lower = content.lower()
                    # 간단한 피싱 차단 키워드(원한다면 DB로도 뺄 수 있음)
                    blocked_keywords = (
                        "discordgift",
                        "discord-airdrop",
                        "nitrodrop",
                        "grabfree",
                        "t.me",
                    )
                    if any(bad in lower for bad in blocked_keywords):
                        await self._delete_and_log(message, "log_spam_reason_link")
                        return

    # 수정으로 악의적 변경 방지
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.guild and not after.author.bot:
            await self.on_message(after)

async def setup(bot: commands.Bot):
    await bot.add_cog(SpamWatchCog(bot))
