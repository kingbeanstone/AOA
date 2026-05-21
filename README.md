# ANR 분석 도구 (aoa2)

VSCode + Cline 환경에서 안드로이드 ANR dumpstate 파일을 자동 분석하는 도구입니다.

## 구조

```
바탕화면\anr-tool\
  ├ install.bat       ← 설치 스크립트
  ├ uninstall.bat     ← 제거 스크립트
  └ payload\
      ├ zz-anr-rule.md   ← Cline 글로벌 룰
      └ anr_parse.py     ← ANR 파서 스크립트
```

## 설치

1. 이 리포지토리를 바탕화면의 `anr-tool` 폴더에 다운로드
2. `install.bat` 실행
3. VSCode 재시작

설치 완료 후 Cline 채팅창에 덤프 파일 경로를 입력하면 분석이 시작됩니다.

## 제거

`uninstall.bat` 실행

## 사용법

```
"C:\path\to\dumpstate.txt 분석해줘"
"이 ANR 덤프 좀 봐줘: C:\dump.txt"
```

## 요구사항

- Python 3.x (표준 라이브러리만 사용 — pip 설치 불필요)
- VSCode + Cline 확장
