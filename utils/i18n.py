from utils.db import get_lang

# 간단 키-문자열 사전
TEXTS = {
    "ko": {
        "setlog_ok": "✅ 로그 채널이 {channel} 으로 설정되었습니다.",
        "setlog_clear": "🧹 로그 채널 설정이 제거되었습니다.",
        "not_set": "⚠️ 로그 채널이 아직 설정되지 않았습니다. 먼저 `/setlog`를 실행하세요.",
        "testlog_title": "🔒 WidowBot 로그 테스트",
        "testlog_body": "이 메시지가 보이면 로그 채널 설정 OK",
        "showconfig": "**로그 채널:** {channel}\n**언어(Language):** {lang}",
        "setlang_ok": "✅ 언어가 `{lang}`(으)로 설정되었습니다.",
        "unknown_error": "❌ 알 수 없는 오류가 발생했습니다.",
        "dm_join_notice": "🔒 보안 안내: 본 서버는 신규/의심 계정을 자동 모니터링합니다. 정상 유저라면 무시하셔도 됩니다. 문제가 있으면 관리자에게 알려주세요.",
        "log_join_title": "⚠️ 경고: 의심 입장 감지",
        "log_join_reason_new": "새 계정(≈{hours}h)",
        "log_join_reason_raid": "단시간 동시 입장 {count}명/{sec}s",
        "log_join_footer_config": "로그 채널은 /setlog 로 변경할 수 있습니다.",
        "log_spam_title": "🚨 스팸/남용 감지",
        "log_spam_footer_config": "스팸 정책은 차후 /spamset 으로 조정 예정",
        "dm_spam_notice": "🔒 안내: 서버의 스팸/남용 방지 정책에 의해 메시지가 제어되었습니다. 문제가 있으면 관리자에게 문의하세요.",
        "log_spam_reason_rate": "단시간 과도한 메시지 ({count} / 10s)",
        "log_spam_reason_everyone": "@everyone/@here 멘션 사용 차단",
        "log_spam_reason_mentions": "멘션 폭탄 (mentions={mentions}, limit={limit})",
        "log_spam_reason_link": "의심스러운 링크/도메인 차단",
        "policies_title": "🔧 현재 정책",
        "policies_body": (
            "**Risk**\n"
            "- 계정 최소 나이: {min_age}h\n- 레이드 판정: {raid_count}명/{raid_win}s\n\n"
            "**Spam**\n"
            "- 10초 최대 메시지: {max_msgs}\n- 1메시지 최대 멘션: {max_mentions}\n"
            "- @everyone/@here 차단: {block_eh}\n- 링크 필터: {link_filter}"
        ),
        "riskset_ok": "✅ Risk 정책이 업데이트되었습니다.",
        "spamset_ok": "✅ Spam 정책이 업데이트되었습니다.",
        "bool_on": "켜짐",
        "bool_off": "꺼짐",
    },
    "en": {
        "setlog_ok": "✅ Log channel set to {channel}.",
        "setlog_clear": "🧹 Log channel setting has been cleared.",
        "not_set": "⚠️ Log channel is not set yet. Please run `/setlog` first.",
        "testlog_title": "🔒 WidowBot Log Test",
        "testlog_body": "If you can see this, logging is configured correctly.",
        "showconfig": "**Log Channel:** {channel}\n**Language:** {lang}",
        "setlang_ok": "✅ Language set to `{lang}`.",
        "unknown_error": "❌ An unknown error occurred.",
        "dm_join_notice": "🔒 Security notice: This server automatically monitors new/suspicious accounts. If you are legit, you can ignore this message. Contact admins if you have issues.",
        "log_join_title": "⚠️ Warning: Suspicious Join Detected",
        "log_join_reason_new": "New account (≈{hours}h)",
        "log_join_reason_raid": "Join surge {count} users/{sec}s",
        "log_join_footer_config": "You can change the log channel with /setlog.",
        "log_spam_title": "🚨 Spam/Abuse Detected",
        "log_spam_footer_config": "Policy adjustable later via /spamset",
        "dm_spam_notice": "🔒 Notice: Your message was moderated by the server's anti-spam policy. Contact admins if this was a mistake.",
        "log_spam_reason_rate": "Excessive message rate ({count} / 10s)",
        "log_spam_reason_everyone": "Blocked @everyone/@here mention",
        "log_spam_reason_mentions": "Mention bomb (mentions={mentions}, limit={limit})",
        "log_spam_reason_link": "Suspicious link/domain blocked",
        "policies_title": "🔧 Current Policies",
        "policies_body": (
            "**Risk**\n"
            "- Min account age: {min_age}h\n- Raid detection: {raid_count} users/{raid_win}s\n\n"
            "**Spam**\n"
            "- Max msgs per 10s: {max_msgs}\n- Max mentions per msg: {max_mentions}\n"
            "- Block @everyone/@here: {block_eh}\n- Link filter: {link_filter}"
        ),
        "riskset_ok": "✅ Risk policy updated.",
        "spamset_ok": "✅ Spam policy updated.",
        "bool_on": "ON",
        "bool_off": "OFF",
    },
}

def t(guild_id: int, key: str, **kwargs) -> str:
    lang = get_lang(guild_id)
    table = TEXTS.get(lang, TEXTS["ko"])
    msg = table.get(key, key)
    if kwargs:
        try:
            msg = msg.format(**kwargs)
        except Exception:
            pass
    return msg
