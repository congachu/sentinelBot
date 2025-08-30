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
