# ANR 분석 도구 (AOA)

VSCode + Cline 환경에서 안드로이드 ANR dumpstate 파일을 자동 분석하는 도구입니다.

## ⬇️ 설치

### Windows

**[anr-install.bat 다운로드](https://github.com/kingbeanstone/AOA/releases/latest/download/anr-install.bat)**  
위 링크 클릭 → 파일 더블클릭 → VSCode 재시작

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

## 제거

- Windows: `uninstall.bat` 실행
- Linux / macOS / WSL: `bash uninstall.sh` 실행

## 사용법

설치 후 Cline 채팅창에 다음 중 하나를 입력하세요.

**방법 1 — 경로 + anr 키워드**
```
C:\path\to\dumpstate.txt anr 분석해줘
/home/user/dumpstate.txt anr 분석해줘
```

**방법 2 — VSCode에 드래그드롭 후 입력**
```
anr 분석해줘
```
> VSCode 탐색기에서 덤프 파일을 Cline 채팅창으로 드래그드롭하면
> 경로가 자동 삽입됩니다. 그 뒤에 `anr 분석해줘` 를 입력하면 됩니다.

## 요구사항

- Python 3.8 이상 (표준 라이브러리만 사용 — pip 설치 불필요)
- VSCode + Cline 확장

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
      ├ zz-anr-rule.md   ← Cline 글로벌 룰
      └ anr_parse.py     ← ANR 파서 스크립트
```
