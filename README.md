# ANR 분석 도구 (AOA)

안드로이드 ANR dumpstate 파일을 자동 분석하는 도구입니다.
**Cline · Cursor · Claude Code** 어디서든 동일하게 동작합니다.

설치 한 번이면 세 툴 모두에 룰이 배치됩니다. 지금 한 툴만 쓰더라도,
나중에 다른 툴을 설치하면 별도 작업 없이 바로 인식됩니다.
(Cline / Claude Code 는 자동, Cursor 만 1회 등록 필요 — 아래 참고)

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

설치 후 AI 어시스턴트 채팅창에 **덤프 경로 + `anr`** 를 입력하세요.

**방법 1 — 경로 + anr 키워드**
```
C:\path\to\dumpstate.txt anr 분석해줘
/home/user/dumpstate.txt anr 분석해줘
```

**방법 2 — 탐색기에서 드래그드롭 후 입력**
```
anr 분석해줘
```
> VSCode/Cursor 탐색기에서 덤프 파일을 에디터 영역으로 드래그드롭합니다.
> 그 뒤에 `anr 분석해줘` 를 입력하면 됩니다.
> (덤프 용량이 크면 채팅창 드롭이 안 될 수 있습니다.)

## 툴별 적용 방법

설치 스크립트가 파서와 룰을 세 툴 모두에 자동으로 배치합니다.

| 툴 | 룰 위치 | 설치 후 할 일 |
|----|--------|-------------|
| **Cline** | `~/Documents/Cline/Rules/zz-anr-rule.md` | VSCode 재시작 |
| **Claude Code** | `~/.claude/CLAUDE.md` 에 import 한 줄 추가 | 없음 (새 세션부터 자동) |
| **Cursor** | Cursor User Rules (state.vscdb) 에 직접 기록 | Cursor 재시작 |

> Cline / Claude Code 는 툴이 아직 없어도 미리 배치합니다.  
> 나중에 설치하면 별도 작업 없이 바로 인식됩니다.  
> Cursor 가 없으면 건너뛰고, 나중에 설치 후 재실행하면 자동 등록됩니다.



## 제거

- Windows: `%USERPROFILE%\.anr-tool\uninstall.bat` 실행
- Linux / macOS / WSL: `bash ~/.anr-tool/uninstall.sh` 실행

> Cline 룰, Claude Code import, Cursor User Rules, 공용 도구 폴더를 모두 정리합니다.  
> `CLAUDE.md` 는 import 한 줄만 제거하고 나머지 내용을 보존합니다.

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
      ├ zz-anr-rule.md   ← 분석 룰 (Cline/Cursor/Claude Code 공용)
      └ anr_parse.py     ← ANR 파서 스크립트
```
