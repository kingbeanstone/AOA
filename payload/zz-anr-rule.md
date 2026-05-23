<!-- 버전: 1.9 -->
# ANR 덤프 분석 — 글로벌 룰

이 룰은 안드로이드 ANR 덤프(dumpstate) 파일 분석 요청을 처리하기 위한
지침이다. 사용자가 ANR 덤프 분석을 요청할 때만 적용한다.

* 필요한 파서: `anr_parse.py` v1.4 이상

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

위 조건에 해당하지 않으면 이 룰은 무시한다.

═══════════════════════════════════════════════════════════════
2. 절대 규칙
═══════════════════════════════════════════════════════════════

1. **원본 덤프 파일을 절대 직접 읽지 말 것.**
   덤프는 수십~수백 MB라 직접 읽으면 컨텍스트가 폭주해 분석 불가.

2. **`_anr_parsed.txt` 만 읽고 분석한다.**
   파서는 분석용 파일(`_anr_parsed.txt`)과 참고용 부록 파일
   (`_anr_crashes.txt`)을 동시에 생성한다. 분석은 전자만 사용한다.

3. **`_anr_crashes.txt` 는 읽지 않는다.**
   이 파일은 사용자가 직접 참고하기 위한 raw dump 이며,
   ANR 분석에는 사용하지 않는다. 보고서에는 파일 경로만 안내한다.

4. **`anr_parse.py` 경로는 OS와 셸에 따라 달라진다. (3절 참고)**

5. **작업 전 반드시 셸 환경을 먼저 확인하고 경로·명령을 결정한다.**

6. **표면 증상에서 멈추지 말 것.** (6절 참고)
   "메인 스레드가 X에서 Waiting" 은 증상일 뿐 원인이 아니다.
   **왜 그 대기가 풀리지 않았는지**까지 추적해야 한다.

7. **로그 라인 끝의 ` … (+N자 절단)` 표시는 파서가 절약을 위해
   라인을 잘랐다는 뜻이다.** 절단된 부분은 보통 객체 dump 의
   세부 필드라 분석에 영향이 없다. 잘린 정보를 추정해서 채우지 말 것.

═══════════════════════════════════════════════════════════════
3. 셸 환경 감지 및 경로·명령 결정 (필수 — 작업 전 1회 수행)
═══════════════════════════════════════════════════════════════

### 3-1. 감지 명령

```
echo $PSVersionTable
```

- 출력 비어 있음/오류 → bash / zsh / CMD
- `PSVersionTable` 출력 → PowerShell

bash/CMD 구분이 필요한 경우: `echo $SHELL`

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

`py` → `python` → `python3` 순으로 재시도. 모두 실패 시 사용자에게
Python 설치 여부 확인 후 중단. 스크립트 파일 자체가 없으면(`No such file`)
설치 스크립트가 실행되지 않은 것이므로 사용자에게 안내하고 중단.

═══════════════════════════════════════════════════════════════
4. 분석 절차
═══════════════════════════════════════════════════════════════

1. 셸 환경 감지 (3절)
2. `anr_parse.py <덤프경로>` 실행
   → `<원본>_anr_parsed.txt` (분석용) 와
     `<원본>_anr_crashes.txt` (참고용 부록) 가 함께 생성됨
3. **`_anr_parsed.txt` 만 읽고 분석.** (`_anr_crashes.txt` 는 읽지 않음)
4. **6절의 근본 원인 추적 체크리스트를 반드시 수행**
5. 보고서를 원본과 같은 디렉토리에 `<원본>_anr_analysis.md` 로 저장
6. 보고서 마지막에 `_anr_crashes.txt` 파일 경로를 한 줄로 안내
7. 환경에 맞는 명령으로 보고서 열기

### 4-1. 보고서 파일 열기 명령

| 환경 | 명령 |
|------|------|
| **PowerShell** | `Invoke-Item "<경로>"` 또는 `Start-Process "<경로>"` |
| **CMD** | `start "" "<경로>"` |
| **bash / zsh** | `xdg-open "<경로>"` (Linux) / `open "<경로>"` (macOS) |

> ⚠️ PowerShell에서 `start "" "경로"` 는 오류 — `Invoke-Item` 사용.

═══════════════════════════════════════════════════════════════
5. 보고서 형식
═══════════════════════════════════════════════════════════════

**파싱 결과 섹션 → 보고서 섹션 매핑**:

| 파싱 결과 (`_anr_parsed.txt`) | 보고서 위치 |
|------------------------------|------------|
| `[1] am_anr` | 0. 기본 정보 |
| `[2] ANR in` | 0. 기본 정보 / 1. 타임라인 |
| `[3] VM TRACES AT LAST ANR` | 2. 콜 스택 |
| `[4] ANR 부근 logcat` | 1. 타임라인 / 3. 서술 항목 근거 |
| `[5] freeze 이전 패키지 로그` | 1. 타임라인 (필요 시) |

> Crash 정보는 분석 입력에 포함되지 않는다.
> `_anr_crashes.txt` 의 존재는 보고서 끝 "부록 안내" 에서만 언급.

### 0. ANR 기본 정보

| 항목 | 내용 |
|------|------|
| 덤프 파일명 | ... |
| ANR 유형 | Input / Broadcast / Service / etc. |
| 발생 프로세스 | com.example.app (PID ...) |
| 발생 시각 | HH:MM:SS |
| 지연 시간 | X ms (am_anr delay 값) |
| 주요 사유 | 한 줄 요약 |

**am_anr 원문 로그 (1줄):**
```
<원문 그대로>
```

### 1. 이벤트 타임라인 표

ANR 원인과 직접 관련된 이벤트만 시간순.

| 시간 | 이벤트 | 상세 |
|------|--------|------|

### 2. 함수 콜 스택 (Trace)

**출처: 파싱 결과 `[3]` 전용.**

- `[3]` 이 `(VM TRACES AT LAST ANR 섹션 없음)` 이면:
  ```
  ANR 없음 — 콜 스택 없음
  ```
- 있으면: 메인 스레드 + 블로킹·락 경합 관련 스레드.
  스레드 상태(`Waiting` / `Blocked` / `Sleeping` / `WaitingForGcToComplete` 등) 표기 필수.
  대기 대상이 있다면 명시 (`waiting on <0x...>`, `held by tid=N` 등).

```
[main] (tid=XX) — [상태]
  at ...
```

### 3. 서술 항목 (본질 추적)

이 섹션은 `_anr_parsed.txt` 의 내용만 사용해서 작성한다.

- **타임라인 요약**: 사건 발생 순서.
- **직접 트리거**: 메인 스레드를 막은 호출 (파일:라인). 표면 증상.
- **블로킹이 풀리지 않은 이유** (6절 체크리스트 결과):
  - 대기 대상이 무엇인가
  - 누가 해제해야 하는가
  - 왜 해제되지 못했는가
- **근본 원인**: 구조적 결함으로 기술.
- **근거**: 파싱 결과의 어느 섹션·라인이 근거인지 인용.
  인용 형식 예시:
  - `[3] VM TRACES`: <스레드명> 상태 <상태값>, <라인 위치>
  - `[4] logcat`: HH:MM:SS <태그> <메시지 요약>
  - `am_anr`: <필드 값>
- **해결 방안**: 근본 원인에 대응하는 구조적 수정안.
  일반론("메인 스레드 막지 마세요")만으로는 부족하다.

### 4. 부록 안내 (마지막 줄)

보고서의 가장 마지막에 다음 한 줄만 추가한다:

```
> Crash 기록(참고용)은 별도 파일 `<원본>_anr_crashes.txt` 에서 확인 가능합니다.
```

이게 전부다. Crash 내용 요약, 해석, 평가, ANR 관련성 언급은 작성하지 않는다.

═══════════════════════════════════════════════════════════════
6. 근본 원인 추적 체크리스트 (필수)
═══════════════════════════════════════════════════════════════

보고서 작성 전 반드시 아래 단계를 수행한다.

### 6-1. 메인 스레드 상태 분류

`[3]` 의 main 스레드 상태에 따라 분기:

| 상태 | 다음 단계 |
|------|----------|
| `Waiting` (object 명시) | 6-2 |
| `Blocked` (waiting to lock) | 6-3 |
| `Native` / `Sleeping` | 6-4 |
| `WaitingForGcToComplete` / `WaitingPerformingGc` | 6-5 (GC 분기) |
| `Runnable` | 6-5 (CPU 분기) |

### 6-2. 동기화 객체 대기 — 해제 책임자 추적

| 대기 대상 | 해제 호출 | 해제 주체 |
|----------|----------|----------|
| `CountDownLatch` | `countDown()` | 다른 스레드/콜백 |
| `Semaphore` | `release()` | 다른 스레드 |
| `Future` | `complete()` / 작업 완료 | 워커 |
| `Condition.await()` | `signal()` / `signalAll()` | 다른 스레드 |
| `Object.wait()` | `notify()` / `notifyAll()` | 다른 스레드 |
| Binder transact | 원격 응답 | 원격 프로세스 |

**핵심 질문:** 해제 주체가 실행될 수 있는 환경인가?

**데드락 패턴 의심:**
- 메인 스레드 대기 → 해제는 메인 스레드 메시지 큐 콜백
  (`ServiceConnection.onServiceConnected`, `BroadcastReceiver.onReceive`,
  `Handler.post`, `runOnUiThread`, RxJava `AndroidSchedulers.mainThread()`,
  Coroutine `Dispatchers.Main`)
- `bindService` + `await`
- `runBlocking { withContext(Dispatchers.Main) { ... } }` on main

### 6-3. 락 경합 / 락 데드락

- 락을 쥔 스레드(`held by tid=N`)의 콜 스택을 함께 확인.
- 그 스레드가 **다른 락을 기다리고 있다면 → 락 데드락 의심.**
  양방향 관계 확인:
  - A: holds L1, waiting for L2
  - B: holds L2, waiting for L1
  → 순환 대기 성립 시 데드락 확정.
- 락 보유 스레드가 다른 작업(I/O, GC, sleep) 중이라면 → 단순 락 보유 지연.

### 6-4. Native / Sleeping

- JNI 호출, 동기 파일/네트워크 I/O, `Thread.sleep` 등.
- StrictMode 위반 가능성.

### 6-5. GC / Runnable

**GC 분기** (`WaitingForGcToComplete` / `WaitingPerformingGc`):
- 다른 스레드들의 할당 패턴 확인 (워커가 무한 할당 중인가?).
- `[4] logcat` 의 `Background concurrent ... GC freed ...` 빈도 확인.
- 할당 속도 > 회수 속도 → GC Thrashing.
- 메인 스레드 자체도 할당 루프에 참여하는지 확인.
- 근거 인용 시 `[3]`, `[4]` 만 사용. 메모리 관련 crash 추정은 금지
  (crash 파일은 본 분석에서 사용하지 않음).
- 용어 정확성: catch 되어 `clear()` 되는 명시적 할당 폭주는
  **메모리 leak 이 아니다**. "leak" 대신 "할당 폭주", "GC Thrashing",
  "가용 메모리 고갈" 같은 정확한 표현을 쓸 것.
- 해결 방안의 본질: "최적화" 가 아니라 "이 할당 루프 자체가 잘못된 설계"
  라는 점을 짚을 것. 무한 루프 안에서 메가바이트급 할당이 발생하는
  코드는 정상적 비즈니스 로직일 수 없음.

**Runnable 분기**:
- 메인 스레드 CPU 집약 작업 (큰 JSON, 이미지 디코딩, 큰 루프).
