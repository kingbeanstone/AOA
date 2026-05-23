<!-- 버전: 1.7 -->
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
- **경로 뒤에 "anr" 키워드만 붙여 입력해도 분석 시작**:
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

3. **작업 전 반드시 셸 환경을 먼저 확인하고 경로·명령을 결정한다.**

4. **표면 증상에서 멈추지 말 것.** (6절 참고)
   "메인 스레드가 X에서 Waiting" 은 증상일 뿐 원인이 아니다.
   **왜 그 대기가 풀리지 않았는지**까지 추적해야 한다.

═══════════════════════════════════════════════════════════════
3. 셸 환경 감지 및 경로·명령 결정 (필수 — 작업 전 1회 수행)
═══════════════════════════════════════════════════════════════

(이전 버전과 동일 — 생략 없이 그대로 유지)

### 3-1. 감지 명령

```
echo $PSVersionTable
```

- 출력이 비어 있거나 오류 → bash / zsh / CMD
- `PSVersionTable` 내용 출력 → PowerShell

bash/CMD 구분이 필요한 경우:

```
echo $SHELL
```

### 3-2. 환경별 경로 및 Python 호출

| 환경 | 스크립트 경로 | Python 실행 순서 |
|------|-------------|------------------|
| **PowerShell** | `"$env:USERPROFILE\.anr-tool\anr_parse.py"` | `py` → `python` → `python3` |
| **CMD** | `"%USERPROFILE%\.anr-tool\anr_parse.py"` | `py` → `python` → `python3` |
| **bash / zsh** | `"$HOME/.anr-tool/anr_parse.py"` | `python3` → `python` |

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

### 3-4. Python 실행 실패 시

`py` → `python` → `python3` 순으로 재시도. 모두 실패 시 사용자 안내 후 중단.

═══════════════════════════════════════════════════════════════
4. 분석 절차
═══════════════════════════════════════════════════════════════

1. 셸 환경 감지 (3절)
2. `anr_parse.py <덤프경로>` 실행 → `<원본>_anr_parsed.txt` 생성
3. 생성된 `_anr_parsed.txt` 만 읽고 분석
4. **6절의 근본 원인 추적 체크리스트를 반드시 수행**
5. 보고서를 원본과 같은 디렉토리에 `<원본>_anr_analysis.md` 로 저장
6. 환경에 맞는 명령으로 보고서 열어주기

### 4-1. 보고서 파일 열기 명령

| 환경 | 명령 |
|------|------|
| **PowerShell** | `Invoke-Item "<경로>"` 또는 `Start-Process "<경로>"` |
| **CMD** | `start "" "<경로>"` |
| **bash / zsh** | `xdg-open` (Linux) / `open` (macOS) |

> PowerShell에서 `start "" "경로"` 는 오류 발생 — 반드시 `Invoke-Item` 사용.

═══════════════════════════════════════════════════════════════
5. 보고서 형식
═══════════════════════════════════════════════════════════════

**파싱 결과 섹션 → 보고서 섹션 매핑**:

| 파싱 결과 | 보고서 |
|---------|--------|
| `[3] VM TRACES AT LAST ANR` | **2. 함수 콜 스택** 전용 |
| `[6] Crash 기록` | **3. Crash 기록** 전용 |

### 0. ANR 기본 정보 (표)

| 항목 | 내용 |
|------|------|
| 덤프 파일명 | ... |
| ANR 유형 | Input dispatching / Broadcast / Service / etc. |
| 발생 프로세스 | com.example.app (PID ...) |
| 발생 시각 | HH:MM:SS |
| 지연 시간 | X ms (am_anr delay 값) |
| 주요 사유 | 한 줄 요약 |

**am_anr 원문 로그 (1줄):**

```
<am_anr 로그 원문 그대로>
```

### 1. 이벤트 타임라인 표

ANR 원인과 직접 관련된 이벤트만 시간순 정리.

| 시간 | 이벤트 | 상세 |
|------|--------|------|

### 2. 함수 콜 스택 (Trace)

**출처: 파싱 결과 `[3]` 전용.**

- `[3]` 이 없으면: `ANR 없음 — 콜 스택 없음` 한 줄.
- 있으면: 메인 스레드 우선 + 블로킹·락 경합 관련 스레드.
  스레드 상태(`Waiting`, `Blocked`, `Sleeping` 등)를 반드시 표기.
- **대기 대상이 있다면 명시**: `waiting on <0x...> (CountDownLatch)`,
  `waiting to lock <0x...> held by tid=N` 등.

```
[main] (tid=XX) — [Waiting on CountDownLatch@0x...]
  at jdk.internal.misc.Unsafe.park(...)
  at java.util.concurrent.locks.LockSupport.park(...)
  at com.example.Foo.bar(Foo.kt:164)
  ...
```

### 3. Crash 기록 (간결 모드)

- 발견 시: **요약 표 + 가장 최근 1건의 raw 로그**만 포함.
- 없으면: `Crash 기록 없음` 한 줄.

| 시간 | 종류 | 프로세스 | 메시지 1줄 |
|------|------|----------|------------|

마지막 crash raw 로그 (tombstone은 backtrace까지만, register/memory map 제외):

```
[JAVA/NATIVE/TOMBSTONE] HH:MM:SS proc=...
FATAL EXCEPTION: ...
  at ...
```

**중요:** 이 섹션은 단순 기록이다. ANR 원인 평가는 **6절**에서.

### 4. 서술 항목 (본질 추적)

- **타임라인 요약**: 사건 발생 순서 (사용자 입력 → 메인 스레드 진입 →
  블로킹 → 타임아웃).
- **직접 트리거**: 메인 스레드를 막은 호출 (파일:라인). 표면 증상.
- **블로킹이 풀리지 않은 이유** (필수, 6절 체크리스트 결과를 여기 정리):
  - 대기 대상이 무엇인가 (lock, latch, future, binder 응답, IPC 등)
  - 누가 그것을 해제해야 했는가 (어느 스레드, 어느 콜백)
  - 그 해제 주체가 왜 실행되지 못했는가
- **근본 원인**: 위 추적의 종착점. 단순 "메인 스레드 블로킹"이 아니라
  **구조적 결함**으로 기술 (예: 메인 스레드에서 메인 스레드 큐로
  디스패치되는 콜백을 동기 대기 → 데드락).
- **근거**: 파싱 결과의 어느 섹션·라인이 위 추론을 뒷받침하는지.
- **해결 방안**: 근본 원인에 대응하는 구조적 수정안. 일반론
  ("메인 스레드 막지 마세요") 만으로는 부족하다.

### 5. ANR 무관 부수 이슈 (있을 때만)

Crash나 권한 오류 등이 ANR과 무관하다고 6절에서 판정된 경우,
이 섹션에서 **별개 이슈로 명시적으로 분리**해서 언급.
ANR 해결 방안 섹션에 섞어 쓰지 말 것.

═══════════════════════════════════════════════════════════════
6. 근본 원인 추적 체크리스트 (필수)
═══════════════════════════════════════════════════════════════

보고서 작성 전 반드시 아래 단계를 머릿속으로(또는 보고서에) 수행한다.

### 6-1. 메인 스레드 상태 분류

`[3]` 의 main 스레드 상태에 따라 분기:

| 상태 | 의미 | 다음 단계 |
|------|------|----------|
| `Waiting` (object 명시) | 동기화 객체 대기 | **6-2** |
| `Blocked` (waiting to lock) | 락 경합 | **6-3** |
| `Native` / `Sleeping` | 네이티브 호출 / sleep | **6-4** |
| `Runnable` | CPU 점유 중 (긴 작업) | **6-5** |

### 6-2. 동기화 객체 대기 — 해제 책임자 추적

대기 대상별로 "누가 해제해야 하는가" 를 파악:

| 대기 대상 | 해제 호출 | 해제 주체 위치 |
|----------|----------|---------------|
| `CountDownLatch` | `countDown()` | 다른 스레드 또는 콜백 |
| `Semaphore` | `release()` | 다른 스레드 |
| `Future` / `CompletableFuture` | `complete()` / 작업 완료 | 워커 스레드 또는 콜백 |
| `Condition.await()` | `signal()` / `signalAll()` | 다른 스레드 |
| `Object.wait()` | `notify()` / `notifyAll()` | 다른 스레드 |
| Binder transact 응답 | 원격 프로세스 응답 | 원격 프로세스 |

**핵심 질문:** 해제 주체가 실행될 수 있는 환경인가?

특히 다음 **데드락 패턴**을 의심:
- 메인 스레드가 대기 → 해제는 **메인 스레드 메시지 큐로 디스패치되는 콜백**에서 수행
  - 예: `ServiceConnection.onServiceConnected`, `BroadcastReceiver.onReceive`,
    `Handler.post`, `runOnUiThread`, RxJava `AndroidSchedulers.mainThread()`,
    Coroutine `Dispatchers.Main`
  - 결과: 메인 스레드가 자기 자신의 콜백을 막아 영원히 대기 → **데드락**
- 동기적 `bindService` + `await` 패턴
- `runBlocking { withContext(Dispatchers.Main) { ... } }` on main

### 6-3. 락 경합

- 락을 쥐고 있는 스레드(`held by tid=N`)의 콜 스택을 함께 확인.
- 그 스레드가 무엇을 하다 락을 못 놓고 있는지가 근본 원인.

### 6-4. Native / Sleeping

- JNI 호출, 파일 I/O, 네트워크 동기 호출, `Thread.sleep` 등.
- Strict mode 위반 가능성.

### 6-5. Runnable

- 메인 스레드에서 CPU 집약 작업 (큰 JSON 파싱, 이미지 디코딩, 큰 루프 등).
- GC 폭주(`art:`, `Background concurrent ... GC`) 동반 여부 확인.

### 6-6. Crash ↔ ANR 인과관계 평가

`[6]` 에 crash 가 있다면 다음 표로 분류:

| 분류 | 조건 | 처리 |
|------|------|------|
| **ANR 원인** | ANR 시각 직전, ANR 프로세스의 메인 스레드 crash, 또는 메인 스레드 대기를 해제할 컴포넌트의 crash | 4 절 "근본 원인" 에 포함 |
| **무관 부수 이슈** | 다른 프로세스의 crash, ANR 시점과 시간차 큼, 메인 스레드 대기와 무관한 컴포넌트 | 5 절 "부수 이슈"에 분리 기재 |

**중요:** 시간상 인접하다는 이유만으로 인과관계를 추정하지 말 것.
**메인 스레드의 대기 해제 경로에 그 컴포넌트가 있는지**가 판단 기준.

예시:
- `AnrService` (Foreground Service) 가 권한 오류로 crash 반복.
  메인 스레드는 `AnrBindService` 에 바인딩하며 latch 대기 중.
  → 두 서비스는 별개. crash는 **무관 부수 이슈**.

═══════════════════════════════════════════════════════════════
7. 키워드 기반 추가 분석 (선택)
═══════════════════════════════════════════════════════════════

1차 보고 후 사용자가 키워드 입력 시:

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

- 복수 키워드: `-k <키워드1> -k <키워드2>`
- 범위: `-b <초>` (ANR 이전), `-a <초>` (ANR 이후). 기본 -120s ~ +10s.

생성된 `<원본>_anr_keyword_<키워드>.txt` 만 읽기.
보고서는 `<원본>_anr_analysis_<키워드>.md` 로 저장 (1차 보고서 덮어쓰기 금지).
