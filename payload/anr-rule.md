<!-- 버전: 2.4 (공식 6분류 재구성) -->
---
name: anr
description: Android ANR dumpstate 자동 분석. 덤프 파일 경로를 받아 파서를 실행하고 근본 원인 분석 보고서를 생성한다.
---

# /anr — Android ANR 덤프 분석

사용자가 `/anr <덤프파일경로>` 형식으로 호출했다.
사용자 메시지에서 덤프 파일 경로를 식별해 파서를 실행하고 분석한다.
경로가 비어 있으면 사용자에게 덤프 파일 경로를 요청하고 중단한다.

* 필요한 파서: `anr_parse.py` v1.39 이상
* 파서 위치:
  * Linux/macOS/WSL: `$HOME/.anr-tool/anr_parse.py`
  * Windows: `%USERPROFILE%\.anr-tool\anr_parse.py`

═══════════════════════════════════════════════════════════════
1. 절대 규칙
═══════════════════════════════════════════════════════════════

1)**원본 덤프 파일을 절대 직접 읽지 말 것.**  

2) 마지막에 "의심가는 프로세스가 있다면 알려주세요.(예: Heimdall 분석해)"라고 출력한다


═══════════════════════════════════════════════════════════════
2. 셸 환경 감지 및 경로·명령 결정 (필수 — 작업 전 1회 수행)
═══════════════════════════════════════════════════════════════

### 2-1. 감지 명령

```
echo $PSVersionTable
```

- 출력 비어 있음/오류 → bash / zsh / CMD
- `PSVersionTable` 출력 → PowerShell

bash/CMD 구분이 필요한 경우: `echo $SHELL`

### 2-2. 환경별 경로 및 Python 호출

| 환경 | 스크립트 경로 | Python 실행 순서 |
|------|-------------|------------------|
| **PowerShell** | `"$env:USERPROFILE\.anr-tool\anr_parse.py"` | `py` → `python` → `python3` |
| **CMD** | `"%USERPROFILE%\.anr-tool\anr_parse.py"` | `py` → `python` → `python3` |
| **bash / zsh** | `"$HOME/.anr-tool/anr_parse.py"` | `python3` → `python` |

### 2-3. 실행 예시

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

### 2-4. Python 실행 실패 시

`py` → `python` → `python3` 순으로 재시도. 모두 실패 시 사용자에게
Python 설치 여부 확인 후 중단. 스크립트 파일 자체가 없으면(`No such file`)
설치 스크립트가 실행되지 않은 것이므로 사용자에게 안내하고 중단.

═══════════════════════════════════════════════════════════════
3. 분석 절차
═══════════════════════════════════════════════════════════════

1. 셸 환경 감지 (2절)
2. `anr_parse.py <덤프경로>` 실행
   → `<원본>_anr_parsed.txt` (분석용) 와
     `<원본>_anr_crashes.txt` (참고용 부록) 가 함께 생성됨
3. **`_anr_parsed.txt` 만 읽고 분석.** (`_anr_crashes.txt` 는 읽지 않음)
4. **5절의 근본 원인 추적 체크리스트를 반드시 수행**
5. 보고서를 원본과 같은 디렉토리에 `<원본>_anr_analysis.md` 로 저장
6. 보고서 마지막에 `_anr_crashes.txt` 파일 경로를 한 줄로 안내
7. 환경에 맞는 명령으로 보고서 열기

### 3-1. 보고서 파일 열기 명령

| 환경 | 명령 |
|------|------|
| **PowerShell** | `Invoke-Item "<경로>"` 또는 `Start-Process "<경로>"` |
| **CMD** | `start "" "<경로>"` |
| **bash / zsh** | `xdg-open "<경로>"` (Linux) / `open "<경로>"` (macOS) |

> ⚠️ PowerShell에서 `start "" "경로"` 는 오류 — `Invoke-Item` 사용.

═══════════════════════════════════════════════════════════════
4. 보고서 형식
═══════════════════════════════════════════════════════════════

**파싱 결과 섹션 → 보고서 섹션 매핑**:

| 파싱 결과 (`_anr_parsed.txt`) | 보고서 위치 |
|------------------------------|------------|
| `[1] am_anr` | 0. 기본 정보 |
| `[2] ANR in` | 0. 기본 정보 / 1. 타임라인 |
| `[3] VM TRACES AT LAST ANR` | 2. 콜 스택 |
| `[4] ANR 부근 logcat` | 1. 타임라인 / 3. 서술 항목 근거 (GC/System/Render/IO/Binder) |
| `[5] ANR-3분 로그` | 1. 타임라인 (필요 시) |


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

### 1. 함수 콜 스택 (Trace)

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

### 2. 이벤트 타임라인 표

ANR 원인과 직접 관련된 이벤트만 시간순.

| 시간 | 이벤트 | 상세 |
|------|--------|------|


### 3. 서술 항목 (본질 추적)

이 섹션은 `_anr_parsed.txt` 의 내용만 사용해서 작성한다.

- **타임라인 요약**: 사건 발생 순서.
- **직접 트리거**: 메인 스레드를 막은 호출 (파일:라인). 표면 증상.
- **블로킹이 풀리지 않은 이유** (5절 체크리스트 결과):
  - 대기 대상이 무엇인가
  - 누가 해제해야 하는가
  - 왜 해제되지 못했는가
- **근본 원인**: 구조적 결함으로 기술. 확신도(상/중/하)를 함께 표기 (5-7).
- **대안 가설**: 차순위 후보가 있으면 한 줄로 남긴다 (없으면 생략).
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

═══════════════════════════════════════════════════════════════
5. 근본 원인 추적 체크리스트 (필수)
═══════════════════════════════════════════════════════════════

보고서 작성 전 반드시 아래를 수행한다.
흐름: **5-0 으로 원인 카테고리 분류 → 5-1 로 진입점 결정 → 5-2~5-7 로 증거 수집.**

### 5-0. 원인 카테고리 (Android 공식 분류)

ANR 의 근본 원인을 아래 6개 중 하나로 **먼저 분류**한다. 분류가 목표이고,
세부 규칙(5-2~5-7)은 그 분류의 증거를 모으는 도구다. 가장 강하게 성립하는
것을 1순위로, 나머지는 교차 점검해 대안 가설로 남긴다.

| # | 카테고리 | 한 줄 정의 | 세부 |
|---|---------|-----------|------|
| 1 | **Deadlock** | 순환 대기 — 서로의 락/자원을 맞물려 영구 정지 | 5-3 |
| 2 | **Lock Contention** | 단일 락을 오래 쥔 스레드 때문에 메인이 대기 | 5-3 |
| 3 | **GPU Hang / Render Stall** | GPU 과점·렌더 파이프라인 지연으로 프레임/입력 정체 | 5-6 |
| 4 | **Slow Binder Call** | 원격 프로세스 응답 지연 (`BinderProxy.transact` 등) | 5-2, 5-7 |
| 5 | **Blocked by Other Component** | 다른 컴포넌트/콜백(서비스·리시버·메인 큐) 대기 | 5-2 |
| 6 | **Generic Slow / Blocking Code** | 메인 스레드 자체의 I/O·GC·CPU 집약·sleep | 5-4, 5-5 |

### 5-1. 진입점: 메인 스레드 상태 → 카테고리 라우팅

`[3]` 의 main 스레드 상태로 어느 카테고리부터 볼지 정한다.
(상태는 출발점일 뿐 — 스택 내용까지 봐야 카테고리가 확정된다.)

| main 상태 | 우선 검토 카테고리 | 진입 |
|----------|------------------|------|
| `Blocked` (waiting to lock) | Deadlock / Lock Contention | 5-3 |
| `Waiting` (object 명시) | Blocked by Other Component / Deadlock | 5-2 |
| `Native` + `BinderProxy.transact` | Slow Binder Call | 5-2(Binder), 5-7 |
| `Native` + 그 외 (JNI/IO/sleep) | Generic Slow | 5-4 |
| `WaitingForGcToComplete` 등 | Generic Slow (GC) | 5-5 |
| `Runnable` | Generic Slow (CPU) 또는 GPU Hang | 5-5, 5-6 |
| 명확한 대기 없음 + 렌더 정황 | GPU Hang / Render Stall | 5-6 |

> `Native` 상태는 Binder 호출일 수도, 단순 I/O 일 수도 있으니 **스택 최상단
> 프레임을 반드시 확인**해 4번(Binder)과 6번(Generic)을 가른다.

### 5-2. 대기 객체 / Binder — 해제 책임자 추적

메인이 무언가를 기다리는 경우(`Waiting`, Binder transact 등), **누가 그것을
풀어야 하는가**를 추적한다.

| 대기 대상 | 해제 주체 |
|----------|----------|
| `Object.wait` / `Condition.await` | `notify`/`signal` 호출 스레드 |
| `CountDownLatch` / `Semaphore` / `Future` | 다른 워커 스레드 |
| `ReentrantLock.lock` | 락 보유 스레드의 `unlock` → 5-3 |
| `BinderProxy.transact` | **원격 프로세스 응답** → Slow Binder Call |

**핵심 질문:** 해제 주체가 실행될 수 있는 환경인가?

**Blocked by Other Component (데드락 변형) 의심:**
- 메인 스레드 대기인데 해제가 **메인 스레드 메시지 큐 콜백**에서 와야 하는 경우
  (`ServiceConnection.onServiceConnected`, `BroadcastReceiver.onReceive`,
  `Handler.post`, `runOnUiThread`, RxJava `mainThread()`, Coroutine `Dispatchers.Main`)
  → 메인이 막혀 있으니 콜백도 영원히 안 옴. 자기참조 데드락.
- `bindService` + `await`, `runBlocking { withContext(Dispatchers.Main) }` on main 등.

**Slow Binder Call:**
- 메인이 `BinderProxy.transact` 에서 Native 대기면, 원격 프로세스(주로
  system_server)가 늦게 응답하는 것. `[2]` CPU 사용량에서 그 프로세스가
  과부하인지, `[4] Binder` 에 `transaction failed`/`timeout` 이 있는지 확인.

### 5-3. Deadlock / Lock Contention

- 락 보유 스레드(`held by tid=N`)의 콜 스택을 함께 확인.
- 보유 스레드가 **또 다른 락을 기다리면** → 순환 대기 확인:
  A holds L1 wait L2 / B holds L2 wait L1 → **Deadlock 확정**.
- 보유 스레드가 다른 작업(I/O·GC·sleep) 중이면 → **Lock Contention**(단순 보유 지연).
- `[5]`/`[4]` 의 `Long monitor contention with owner ...`, `dvm_lock_sample` 은
  Android 가 감지한 락 경합 직접 단서.

### 5-4. Generic Slow — Native / Sleeping

- JNI 호출, 동기 파일/네트워크 I/O, `Thread.sleep`, StrictMode 위반 등.
- 메인 스레드 자체가 느린 작업을 직접 수행 중인 경우.

### 5-5. Generic Slow — GC / CPU

- **GC**(`WaitingForGcToComplete` 등): 다른 스레드 할당 패턴 확인.
  할당 속도 > 회수 속도면 GC Thrashing. catch 후 `clear()` 되는 할당 폭주는
  leak 이 아니라 "할당 폭주/GC Thrashing"으로 표현.
- **CPU**(`Runnable`): 메인 스레드 CPU 집약 작업 (큰 JSON, 이미지 디코딩, 큰 루프).

### 5-6. GPU Hang / Render Stall

메인이 명확한 락/대기에 안 걸렸는데 ANR 이 났거나, 다른 앱이 GPU 를 과점한
정황이 의심될 때.

- `[4] Render` 의 `Davey! duration=...ms` 는 UI 스레드 프레임이 그만큼 멈췄다는 뜻.
- **frameNumber 가 ANR 구간 내내 큰 폭으로 끊김 없이 증가 + `avgGpuLoad` 포화(90+)**
  면 GPU 지속 점유의 강한 신호. 락/HAL 보유 해제 책임자가 렌더·GPU 경로에서
  지연됐다면 GPU Hang 을 1순위로 의심.
- **써멀 스로틀링:** `SIOP_GPU_FREQ_MAX`, `GPUMaxFreq`, `GPUFreqMax`,
  `HYPER-HAL`/`SemDvfsHyPerManager` 의 GPU 클럭 상한이 보이면 발열로 성능 제한.

### 5-7. 확신도 / 근거 정리

후보가 둘 이상이거나 확신이 낮을 때, 각 후보를 상/중/하로 평가:
- **직접성**: 메인을 막은 호출과 직접 연결되는가, 정황인가.
- **시간 일치**: 해당 로그/상태 시각이 ANR 지연 구간과 겹치는가.
- **교차 일치**: `[3]`·`[4]`·`[5]` 중 둘 이상이 같은 결론인가.
- **인과 역전 점검**: 직접 증상과 배경 원인(그 대기를 못 풀게 한 것)을 구분.
  직접성이 높다고 자동 1순위가 아니다 — 배경 원인이 없었으면 ANR 이 안 났을
  정황이면 배경 원인 점수를 더 높게.

### 추론 제한 규칙

직접 근거가 없으면 "왜 해제되지 못했는가"는 **가장 가까운 확인 가능한 원인까지만**
기술한다. 그 이후 단계는 추정 또는 대안 가설로 분리한다.


═══════════════════════════════════════════════════════════════
6. 키워드 기반 2차 분석 (선택)
═══════════════════════════════════════════════════════════════

1차 보고 후 사용자가 특정 키워드로 더 파고들기를 요청하면
(예: "Heimdall 로 2차 분석해", "freeze 키워드로 더 봐줘") 아래 절차를 따른다.

### 6-1. 키워드 모드 재파싱

`anr_parse.py` 에 `-k <키워드>` 를 붙여 다시 실행한다.


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

- **복수 키워드:** `-k <키워드1> <키워드2>` 또는 `-k <키워드1> -k <키워드2>` (하나라도 포함되면 매칭)

### 6-2. 결과 읽기 및 보고서

- `-k` 결과는 `_anr_parsed.txt` 맨 뒤에 `[K] 키워드: <키워드>` 섹션으로 추가된다.
  그 섹션을 읽고 분석한다 (원본 덤프 직접 읽기 금지).
- `[K]` 섹션은 노이즈 필터·압축 없이 원본 줄 그대로 (라인 절단만 적용).
- 1차 보고서(`_anr_analysis.md`)는 덮어쓰지 않는다.
  2차 보고서는 `<원본>_anr_analysis_<키워드>.md` 로 저장한다 (이력 보존).
- 키워드 결과가 비어 있으면("매칭 라인 없음") 추정으로 채우지 말고
  "해당 키워드의 로그가 분석 범위(ANR-180s ~ ANR) 내에 없음"을 그대로 보고한다.
