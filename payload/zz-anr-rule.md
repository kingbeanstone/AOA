<!-- 버전: 1.4 -->
# ANR 덤프 분석 — 글로벌 룰

이 룰은 안드로이드 ANR 덤프(dumpstate) 파일 분석 요청을 처리하기 위한
지침이다. 사용자가 ANR 덤프 분석을 요청할 때만 적용한다.

═══════════════════════════════════════════════════════════════
1. 적용 조건 (Trigger)
═══════════════════════════════════════════════════════════════

다음 중 하나에 해당하면 이 룰을 적용한다:

- 사용자가 덤프 파일(dumpstate, ANR 로그 등) 경로를 주며 "분석",
  "ANR 봐줘", "원인 찾아줘", "anr" 등을 요청
- 파일명에 `dumpstate`, `anr`, `bugreport` 등이 포함되어 있고
  분석 의도가 명확한 경우
- **경로 뒤에 "anr" 키워드만 붙여 입력해도 분석 시작** (가장 간단한 사용법):
  - Windows: `C:\path\to\dumpstate.txt anr`
  - Linux / macOS / WSL: `/home/user/dumpstate.txt anr`

위 조건에 해당하지 않으면 이 룰은 무시한다 (일반 작업 방해 금지).

═══════════════════════════════════════════════════════════════
2. 절대 규칙
═══════════════════════════════════════════════════════════════

1. **원본 덤프 파일을 절대 직접 읽지 말 것.**
   덤프는 수십~수백 MB라 직접 읽으면 컨텍스트가 폭주해 분석 불가.
   반드시 `anr_parse.py` 로 파싱한 결과 파일만 읽는다.

2. **`anr_parse.py` 경로는 OS와 셸에 따라 달라진다. (3절 참고)**
   다른 위치를 가정하지 말 것.

3. **작업 전 반드시 셸 환경을 먼저 확인하고 경로·명령을 결정한다.**

═══════════════════════════════════════════════════════════════
3. 셸 환경 감지 및 경로·명령 결정 (필수 — 작업 전 1회 수행)
═══════════════════════════════════════════════════════════════

분석 요청을 받으면 **터미널 명령을 실행하기 전에 반드시** 아래 감지
절차를 수행한다. 이미 이번 대화에서 감지를 완료한 경우에는 생략해도 된다.

### 3-1. 감지 명령

다음 명령 하나를 실행한다:

```
echo $PSVersionTable
```

- **출력이 비어 있거나 오류** → bash / zsh / CMD 중 하나
- **`PSVersionTable` 내용이 출력됨** → PowerShell (pwsh 또는 Windows PowerShell)

bash/CMD 구분이 필요한 경우 추가로:

```
echo $SHELL
```

- `/bin/bash`, `/bin/zsh` 등이 출력 → Unix 계열 셸 (bash/zsh)
- 빈 출력 또는 오류 → Windows CMD

### 3-2. 환경별 `anr_parse.py` 경로 및 Python 호출 방식

| 환경 | 스크립트 경로 | Python 실행 순서 |
|------|-------------|------------------|
| **PowerShell** (Windows) | `"$env:USERPROFILE\.anr-tool\anr_parse.py"` | `py` → `python` → `python3` |
| **CMD** (Windows) | `"%USERPROFILE%\.anr-tool\anr_parse.py"` | `py` → `python` → `python3` |
| **bash / zsh** (Linux·macOS·WSL) | `"$HOME/.anr-tool/anr_parse.py"` | `python3` → `python` |

`anr_parse.py` 는 표준 라이브러리만 사용 → pip 설치 불필요.

### 3-3. 실행 예시

**PowerShell:**
```powershell
py "$env:USERPROFILE\.anr-tool\anr_parse.py" "<덤프경로>"
```

**CMD:**
```cmd
py "%USERPROFILE%\.anr-tool\anr_parse.py" "<덤프경로>"
```

**bash / zsh:**
```bash
python3 "$HOME/.anr-tool/anr_parse.py" "<덤프경로>"
```

### 3-4. Python 실행 실패 시 처리

- `py` 가 없으면 `python`, 그래도 없으면 `python3` 순으로 재시도.
- 세 가지 모두 실패하면 사용자에게 Python 설치 여부를 확인하고 중단.
- 스크립트 파일 자체가 없으면(`No such file` 등) 설치 스크립트가
  실행되지 않은 것이므로 사용자에게 안내하고 중단.

═══════════════════════════════════════════════════════════════
4. 분석 절차
═══════════════════════════════════════════════════════════════

사용자가 자연어로 ANR 분석을 요청하면 다음 절차를 따른다:

1. **셸 환경 감지** (3절) → 경로·명령 형식 결정
2. `anr_parse.py <덤프경로>` 실행 → `<원본>_anr_parsed.txt` 생성
3. 생성된 `_anr_parsed.txt` 파일만 읽고 분석
4. 원인 분석 보고서를 **원본 덤프와 같은 디렉토리**에
   `<원본>_anr_analysis.md` 로 저장
5. 저장 경로를 사용자에게 알려주고, 환경에 맞는 명령으로 파일을 열어준다

### 4-1. 보고서 파일 열기 명령 (환경별)

| 환경 | 명령 |
|------|------|
| **PowerShell** | `Invoke-Item "<경로>"` 또는 `Start-Process "<경로>"` |
| **CMD** | `start "" "<경로>"` |
| **bash / zsh** | `xdg-open "<경로>"` (Linux) / `open "<경로>"` (macOS) |

> ⚠️ **PowerShell에서 `start "" "경로"` 는 오류 발생** — `Start-Process`의
> 첫 번째 인수가 빈 문자열이면 유효성 검사에서 실패한다.
> PowerShell에서는 반드시 `Invoke-Item` 또는 `Start-Process "<경로>"` 를 쓴다.

═══════════════════════════════════════════════════════════════
5. 보고서 형식
═══════════════════════════════════════════════════════════════

보고서(`_anr_analysis.md`)는 다음 구조를 따른다.

**파싱 결과 섹션 → 보고서 섹션 매핑 (엄격히 준수)**:

| 파싱 결과 섹션 | 보고서에 쓰는 곳 |
|--------------|----------------|
| `[3] VM TRACES AT LAST ANR` | **2. 함수 콜 스택** 전용 |
| `[6] Crash 기록` | **3. Crash 기록** 전용 |

이 매핑 외의 데이터(예: `[6]`의 스택을 `2. 콜 스택`에 쓰는 것)는 **절대 금지**.

### 0. ANR 기본 정보 (표)

| 항목 | 내용 |
|------|------|
| 덤프 파일명 | ... |
| ANR 유형 | Input dispatching timed out / Broadcast of Intent / Service / etc. |
| 발생 프로세스 | com.example.app (PID ...) |
| 발생 시각 | HH:MM:SS |
| **지연 시간** | **X ms** (am_anr 로그의 delay 값. 확인 불가 시 명시) |
| 주요 사유 | (한 줄 요약) |

**am_anr 원문 로그 (1줄):**
```
<am_anr 로그 원문을 그대로 1줄 인용. 없으면 "am_anr 로그 없음" 명시>
```
예시: `04-14 10:37:42.950  1000  4401 24946 I am_anr  ( 4401): [0,24946,com.example.app,1001,Input dispatching timed out,5000]`

확인 불가 항목은 "확인 불가"로 표시.

### 1. 이벤트 타임라인 표

**ANR 원인과 직접 관련된 이벤트만** 시간순 정리.
특히 **ANR을 유발한 입력 이벤트**(터치/키, input dispatching timeout 등)는
반드시 포함. 무관한 정상 로그는 제외.

| 시간 | 이벤트 | 상세 |
|------|--------|------|
| ... | ... | ... |

### 2. 함수 콜 스택 (Trace)

**출처: 파싱 결과 `[3] VM TRACES AT LAST ANR` 섹션 전용.**

파싱 결과 `[3]`을 확인하고 아래 분기를 따른다:

**① `[3]` 내용이 `(VM TRACES AT LAST ANR 섹션 없음)` 이면** — 아래 한 줄만 작성하고 끝낸다:
```
ANR 없음 — 콜 스택 없음
```

**② `[3]` 에 스레드 덤프가 있으면** — 메인 스레드 우선, 블로킹·락 경합 관련 스레드도 함께. 코드 블록으로 출력:
```
[main] (tid=XX)  — [상태: Sleeping / Blocked / ...]
  at com.example.Foo.bar(Foo.java:123)
  at com.example.Baz.qux(Baz.java:456)
  ...

[Binder:1234_1] (tid=YY)  — [Blocked, waiting on lock held by main]
  at ...
```

> `[6] Crash 기록`의 스택은 아래 3절에서만 표시한다. 절대 이 섹션에 쓰지 않는다.

### 3. Crash 기록

crash / fatal exception / tombstone / native crash / signal 발견 시
**별도 항목으로 표시**. 없으면 `Crash 기록 없음` 명시.

먼저 발견된 crash 목록을 요약 표로:

| 시간 | 종류 | 프로세스 | 상세 |
|------|------|----------|------|
| ... | JAVA / NATIVE / TOMBSTONE | ... | ... |

**마지막(가장 최근) crash 1건의 raw 로그 전문**을 코드 블록에 그대로 포함한다.
파싱 결과 `[6] Crash 기록`에서 시간상 가장 마지막 엔트리를 골라,
헤더(시간/종류/proc) + FATAL EXCEPTION + 전체 스택(Caused by 체인 포함)을
**파서 출력 원문 그대로** 출력한다. 요약·생략·재구성 금지.

```
[JAVA/NATIVE/TOMBSTONE]  HH:MM:SS  proc=com.example.app
FATAL EXCEPTION: main
java.lang.NullPointerException: ...
  at com.example.Foo.bar(Foo.java:123)
  at ...
Caused by: ...
  at ...
```

> 주의:
> - 이전 crash들은 요약 표에만 기록하고, 본문 로그는 반복 출력하지 않는다 (토큰 절약).
> - 코드 블록 안 라인은 들여쓰기·공백 그대로 보존.
> - tombstone인 경우 register dump·memory map은 제외하고 **backtrace 섹션까지만** 포함한다 (수백 줄 폭증 방지).

### 4. 서술 항목

- **타임라인 요약**: 사건 발생 순서로 본 시나리오
- **근본 원인 추정**: 어떤 이벤트가 ANR 트리거였는지
- **근거**: 파싱 결과 중 어느 부분이 근거인지
- **해결 방안**: 권장 조치 (메인 스레드 작업 분리, 락 범위 축소,
  바인더 호출 비동기화 등)

═══════════════════════════════════════════════════════════════
6. 키워드 기반 추가 분석 (선택)
═══════════════════════════════════════════════════════════════

1차 보고 후 사용자가 특정 키워드를 추가로 입력하면:

1. 키워드 모드 재파싱 (환경에 맞는 경로·명령 사용):

   **PowerShell:**
   ```powershell
   py "$env:USERPROFILE\.anr-tool\anr_parse.py" "<덤프경로>" -k <키워드>
   ```
   **CMD:**
   ```cmd
   py "%USERPROFILE%\.anr-tool\anr_parse.py" "<덤프경로>" -k <키워드>
   ```
   **bash / zsh:**
   ```bash
   python3 "$HOME/.anr-tool/anr_parse.py" "<덤프경로>" -k <키워드>
   ```

   - 복수: `-k <키워드1> -k <키워드2>`
   - 범위: `-b <초>`(ANR 이전), `-a <초>`(ANR 이후)
     (기본 -120s ~ +10s. Heimdall처럼 ANR 한참 전부터 동작하는
     프로세스 추적 시 `-b 300` 권장)

2. 생성된 `<원본>_anr_keyword_<키워드>.txt` 만 읽고 분석.
   (1차 `_anr_parsed.txt` 보존)

3. 보고서: `<원본>_anr_analysis_<키워드>.md` 로 저장.
   1차 `_anr_analysis.md` 는 **덮어쓰지 않는다** (이력 보존).

**키워드 모드에서도 원본 덤프 직접 읽기 금지.
반드시 `_anr_keyword_<키워드>.txt` 결과 파일만 읽는다.**
