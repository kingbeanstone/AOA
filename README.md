# ANR 분석 도구 (AOA)

안드로이드 ANR dumpstate 파일을 자동 분석하는 도구입니다.
**Cline · Cursor · Claude Code** 어디서든 동일하게 `/anr` 슬래시 커맨드로 동작합니다.

설치 한 번이면 세 툴 모두에 `/anr` 커맨드가 배치됩니다.
지금 한 툴만 쓰더라도, 나중에 다른 툴을 설치하면 별도 작업 없이 바로 인식됩니다.

## ⬇️ 설치

### Windows

**[anr-install.bat 다운로드](https://github.com/kingbeanstone/AOA/releases/latest/download/anr-install.bat)**  
위 링크 클릭 → 파일 더블클릭

> 최신 버전을 GitHub에서 자동으로 받아 설치합니다.  
> 업데이트할 때도 같은 파일을 다시 실행하면 됩니다.

### Linux / macOS / WSL

터미널에 아래 명령어를 붙여넣으세요.

```bash
curl -fsSL https://raw.githubusercontent.com/kingbeanstone/AOA/main/anr-install.sh | bash
```

> curl이 없으면: `wget -qO- <위 URL> | bash`

> **오프라인 환경** — GitHub 연결에 실패하면 스크립트와 같은 폴더의
> `payload/` 폴더에서 자동으로 폴백합니다.

## 사용법

설치 후 AI 어시스턴트 채팅창에 `/anr` 커맨드와 덤프 파일 경로를 입력하세요.

```
/anr C:\path\to\dumpstate.txt
/anr /home/user/dumpstate.txt
/anr ~/Downloads/bugreport.txt
```

> 탐색기에서 덤프 파일을 드래그드롭한 뒤 `/anr` 만 입력해도 됩니다.

## 툴별 적용 방법

설치 스크립트가 파서와 `/anr` 정의 파일을 세 툴 모두에 자동으로 배치합니다.

| 툴 | `/anr` 파일 위치 | 설치 후 할 일 |
|----|------------------|-------------|
| **Claude Code** | `~/.claude/commands/anr.md` | 없음 (새 세션부터 즉시) |
| **Cline** | `~/.cline/skills/anr/SKILL.md` | VSCode 재시작 |
| **Cursor** | `~/.cursor/skills/anr/SKILL.md` | Cursor 재시작 |

> 세 툴 모두 슬래시 커맨드 / 워크플로우 / 스킬 네이티브 기능을 사용합니다.  
> 글로벌 룰을 주입하는 방식이 아니므로 사용자가 `/anr` 호출할 때만 동작합니다.  
> 툴이 아직 설치되지 않아도 파일은 미리 배치됩니다 — 나중에 설치 시 바로 인식.

## 제거

- Windows: `%USERPROFILE%\.anr-tool\uninstall.bat` 실행
- Linux / macOS / WSL: `bash ~/.anr-tool/uninstall.sh` 실행

> 신버전(슬래시 커맨드 파일) + 구버전(글로벌 룰) 잔재 모두 정리합니다.  
> `CLAUDE.md` 에 옛 import 한 줄이 남아 있으면 그것만 제거하고 나머지는 보존합니다.

## 요구사항

- Python 3.8 이상 (표준 라이브러리만 사용 — pip 설치 불필요)
- Cline / Cursor / Claude Code 중 하나 이상

## 구조

```
AOA/
  ├ anr-install.bat  ← 설치 스터브 (Windows용 배포 파일)
  ├ anr-install.sh   ← 설치 스터브 (Linux / macOS / WSL 배포 파일)
  ├ install.bat      ← 설치 스크립트 본체 (Windows)
  ├ install.sh       ← 설치 스크립트 본체 (Linux / macOS / WSL)
  ├ uninstall.bat    ← 제거 스크립트 (Windows)
  ├ uninstall.sh     ← 제거 스크립트 (Linux / macOS / WSL)
  └ payload/
      ├ anr-rule.md      ← /anr 커맨드/스킬 본문 (Cline/Cursor/Claude Code 공용)
      └ anr_parse.py     ← ANR 파서 스크립트
```
