# SentinelBot

[🇰🇷 한국어](#-한국어) | [🇺🇸 English](#-english)

---

## 🇰🇷 한국어

### 주요 기능
- **정책 관리**
  - `/policies` : 정책 확인
  - `/riskset` : 계정 나이·레이드 탐지 임계값 설정
  - `/spamset` : 스팸·멘션 폭탄·링크 필터 정책 설정
  - `/spamallow` : @everyone/@here 화이트리스트 관리 (add/remove/list)
  - `/lockdownset` : 신규/의심 계정 차단 임계값 설정

- **신규 유저 감시**
  - 계정 나이 검증
  - 레이드(단시간 다수 입장) 탐지
  - 로그 기록 + DM 안내

- **메시지 감시**
  - 메시지 속도 제한 (10초 내 메시지 횟수)
  - 멘션 폭탄 / @everyone 남용 차단 (화이트리스트 예외 지원)
  - 피싱·사기 링크 필터링

- **자동 제재 (Auto Enforcement)**
  - 도배/피싱: 임계값 초과 + 30분 내 추가 10회 → **BAN**
  - @everyone/@here: 2분 내 3회 → **BAN** (화이트리스트 제외)
  - 신규 저연령 계정 → **KICK**
  - 레이드 급증 → **BAN**

- **비상 제어**
  - `/panic` : 모든 채널 읽기 전용화
  - `/unpanic` : 원복
  - `/lockdown` : 신규/의심 계정 차단 토글

- **백업 & 복구**
  - `/backup_create` : 서버 구조 백업
  - `/backup_restore` : 백업 복구 (비파괴)
  - `/backup_list`, `/backup_delete`

- **보안 점검**
  - `/security_audit` : 서버 보안 점수 및 취약점 리포트 제공

### 🤖 봇 초대하기
[👉 SentinelBot 초대하기](https://discord.com/oauth2/authorize?client_id=1312637093251383356)

---

## 🇺🇸 English

### Key Features
- **Policy Management**
  - `/policies` : View current policies
  - `/riskset` : Configure account age / raid thresholds
  - `/spamset` : Configure spam / mention bomb / link filter
  - `/spamallow` : Manage @everyone/@here whitelist (add/remove/list)
  - `/lockdownset` : Block suspicious account thresholds

- **Join Watch**
  - Account age verification
  - Raid detection (many joins quickly)
  - Logs + DM notifications

- **Message Watch**
  - Rate limit (messages in 10s)
  - Mention bomb / @everyone abuse block (with whitelist exception)
  - Phishing / scam link filtering

- **Auto Enforcement**
  - Spam/Phishing: threshold breach + 10 more within 30min → **BAN**
  - @everyone/@here: 3 times within 2 minutes → **BAN** (whitelisted roles exempt)
  - Young new account → **KICK**
  - Raid surge → **BAN**

- **Admin Controls**
  - `/panic` : Read-only all channels
  - `/unpanic` : Restore
  - `/lockdown` : Toggle suspicious account blocking

- **Backup & Restore**
  - `/backup_create` : Backup server structure
  - `/backup_restore` : Restore backup (non-destructive)
  - `/backup_list`, `/backup_delete`

- **Security Audit**
  - `/security_audit` : Provides security score & vulnerabilities report

### 🤖 Invite the Bot
[👉 Invite SentinelBot](https://discord.com/oauth2/authorize?client_id=1312637093251383356)
