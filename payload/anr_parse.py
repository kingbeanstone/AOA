#!/usr/bin/env python3
"""
anr_parse.py
dumpstate 파일에서 ANR 관련 섹션을 추출해 두 개의 텍스트 파일로 분리 저장.

사용법:
  python anr_parse.py <dumpstate_path>
  또는 실행 후 경로 드래그/입력

출력 파일 1: <원본>_anr_parsed.txt  (분석용 — LLM 이 읽는 파일)
  [1] am_anr       — logcat am_anr 이벤트
  [2] ANR in       — ActivityManager ANR 헤더 + CPU 사용량 + PSI 메모리
  [3] VM traces    — VM TRACES AT LAST ANR 스레드 덤프
  [4] 부근 logcat  — ANR-180s ~ ANR 시점 키워드 (GC/System/Render/IO)
  [5] ANR-3분 로그 — ANR-180s ~ ANR 시점 ANR 패키지 관련 로그

출력 파일 2: <원본>_anr_crashes.txt  (참고용 — ANR 분석에 사용하지 않음)
  [A] Crash 기록   — Java / native crash / TOMBSTONE (파일 전체 스캔)

* Crash 정보를 별도 파일로 분리한 이유:
  LLM 이 ANR 본문 분석 중에 crash 로그를 끌어들여
  무관한 인과관계를 만들어내는 패턴을 차단하기 위함.
  사용자가 필요할 때만 _anr_crashes.txt 를 직접 확인한다.

* 라인 절단 (v1.4~):
  [4] / [5] 의 각 로그 라인을 500자로 절단한다.
  Android 시스템 로그가 한 줄에 객체 전체를 직렬화해 박는 경우
  (TaskInfo, TransitionRequestInfo, InsetsController 등),
  분석에는 앞부분만으로 충분하면서 토큰량이 폭증하는 것을 막는다.

* 노이즈 태그 필터 (v1.5~):
  [5] 로그에서 ANR 분석과 무관한 태그들을 제거한다.
  4 케이스(락 데드락 / ReentrantLock / 락 보유 지연 / GC 압박) 교차 검증으로
  안전성 확인됨. 그래픽 파이프라인(SurfaceFlinger 등), Insets 상태 변화,
  트랜지션 디테일, 패키지 가시성 정책, 삼성 OEM 모듈 등.
  WindowManager / HWUI 는 메시지 패턴으로 추가 필터링
  (WindowManager: focus 변경·WIN DEATH 만 유지 / HWUI: Davey! 만 유지).
  SDHMS(삼성 PID 컨트롤러) 는 GPU·온도 스로틀링 시그널이 필요해서
  필터에서 빼고 압축에만 맡긴다.

* ANR-3분 로그 ([5], v1.9~):
  ANR 시점 300초 전부터 ANR 시점까지 ANR 패키지명이 포함된 로그를 추출한다.
  1차 분석의 안정적인 베이스라인 — 가설 없이 항상 동일한 기준으로 본다.

* 키워드 2차 분석 (-k, v1.7~):
  python anr_parse.py "<덤프>" -k <키워드> [-k <키워드2> ...]
  1차 분석은 ANR 패키지 기준, 2차는 사용자가 의심하는 관련 프로세스/모듈 키워드 기준.
  매칭 조건만 다르고 처리(윈도우 ANR-180s, 노이즈 필터, 압축, 라인 절단)는 1차와 동일.
  결과는 <원본>_anr_keyword_<키워드>.txt 로 저장된다 (1차 결과 보존).
  예) 1차에서 wallpaper 가 GPU 과점한 흔적이 보이면 → -k wallpaper 로 검증.
      노이즈 필터에 걸리는 태그 자체를 보고 싶다면 → -k BLASTBufferQueue 등.

외부 라이브러리 불필요 (표준 라이브러리만 사용).
Python 3.8 이상 호환.
"""

import os
import re
import sys
from datetime import datetime as _dt
from typing import Optional

__version__ = "1.34"


# ──────────────────────────────────────────────────────────────────────────────
# 파일 라인 캐시: 한 dumpstate 를 디스크에서 한 번만 읽는다
# ──────────────────────────────────────────────────────────────────────────────
# 16개 추출 함수가 각자 open() 으로 파일을 처음부터 다시 읽으면 큰 덤프(수백MB)
# 에서 I/O 가 함수 수만큼 곱절로 든다. break 제거로 끝까지 읽게 되면서 체감 큼.
# 모듈 레벨 캐시로 (path, mtime) 키에 라인 리스트를 보관해 두 번째부터는 메모리
# 접근만 한다. 라인은 원본 그대로(개행 포함) 보관해 기존 코드 동작과 호환.
_LINE_CACHE = {}  # (abs_path, mtime) -> list[str]


def _read_lines(path: str):
    try:
        st = os.stat(path)
        key = (os.path.abspath(path), st.st_mtime)
    except OSError:
        key = (os.path.abspath(path), None)
    cached = _LINE_CACHE.get(key)
    if cached is not None:
        return cached
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    _LINE_CACHE[key] = lines
    return lines


# logcat 섹션 헤더/푸터 (dumpstate 표준 형식)
#   시작: ------ SYSTEM LOG (logcat ...) ...
#         ------ EVENT LOG (logcat ...) ...
#   끝:   ------ 3.200s was the duration of 'SYSTEM LOG' ------
_LOGCAT_SECTION_START = re.compile(
    r"^------\s+(SYSTEM LOG|EVENT LOG)\b", re.IGNORECASE
)
_LOGCAT_SECTION_END = re.compile(
    r"^------\s+[\d.]+s was the duration of '(SYSTEM LOG|EVENT LOG)'",
    re.IGNORECASE,
)
# 또는 다른 섹션이 시작되면 logcat 섹션 종료 (안전망)
_ANY_SECTION_START = re.compile(r"^------\s+\S")


def _read_logcat_lines(path: str):
    """dumpstate 에서 SYSTEM LOG / EVENT LOG 섹션만 잘라 반환.
    ANR 분석에 필요한 logcat 은 거의 이 두 버퍼에 있고, 나머지 섹션(stat dumps,
    package services, traces 등)은 logcat 처럼 보이는 줄이 일부 섞여 있어도
    노이즈가 되거나 시간 윈도우 밖이라 비용만 든다. 이 헬퍼는 4·5·키워드
    추출이 보는 범위를 두 버퍼로 좁혀 큰 덤프에서 체감 속도를 크게 줄인다.
    캐시는 _read_lines 와 별도 키로 보관한다."""
    try:
        st = os.stat(path)
        key = ("logcat_only", os.path.abspath(path), st.st_mtime)
    except OSError:
        key = ("logcat_only", os.path.abspath(path), None)
    cached = _LINE_CACHE.get(key)
    if cached is not None:
        return cached

    out = []
    in_sec = False
    sec_name = None
    for line in _read_lines(path):
        if in_sec:
            # 명시적 종료 마커
            if _LOGCAT_SECTION_END.match(line):
                in_sec = False
                sec_name = None
                continue
            # 종료 마커 누락 시 안전망: 다른 섹션 헤더가 나오면 종료
            if _ANY_SECTION_START.match(line) and not _LOGCAT_SECTION_START.match(line):
                in_sec = False
                sec_name = None
                # 새 헤더가 또 SYSTEM/EVENT LOG 인지 아래에서 다시 검사
            else:
                out.append(line)
                continue
        m = _LOGCAT_SECTION_START.match(line)
        if m:
            in_sec = True
            sec_name = m.group(1).upper()
            continue

    # 섹션이 하나도 안 잡혔으면 — 헤더가 없는 변형 덤프 — 전체로 fallback
    if not out:
        out = _read_lines(path)
    _LINE_CACHE[key] = out
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 공통: logcat 타임스탬프 → float 초
# ──────────────────────────────────────────────────────────────────────────────

def _logcat_ts(line: str):
    """MM-DD HH:MM:SS.mmm → 연초 기준 누적 초(float). 파싱 실패 시 None."""
    m = re.match(r"(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d+)", line)
    if not m:
        return None
    mon, day, hr, mn, sc, frac = m.groups()
    try:
        yday = (_dt(2000, int(mon), int(day)) - _dt(2000, 1, 1)).days
        return yday * 86400 + int(hr) * 3600 + int(mn) * 60 + int(sc) + int(frac[:6].ljust(6, "0")) / 1e6
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 공통: 마지막 ANR 프로세스 정보 추출
# ──────────────────────────────────────────────────────────────────────────────

def _last_anr_info(path: str):
    """마지막 am_anr 이벤트에서 (pid, process_name) 반환. 없으면 (None, None)."""
    pid, proc = None, None
    for line in _read_logcat_lines(path):
        if " am_anr" in line:
            m = re.search(r"am_anr\s*:\s*\[\d+,(\d+),([^,]+),", line)
            if m:
                pid, proc = m.group(1), m.group(2)
    return pid, proc


# ──────────────────────────────────────────────────────────────────────────────
# [1] am_anr 이벤트
# ──────────────────────────────────────────────────────────────────────────────

def extract_am_anr(path: str) -> str:
    """마지막 ANR 프로세스의 am_anr 이벤트만 추출."""
    _, proc = _last_anr_info(path)
    if proc is None:
        return "(am_anr 이벤트 없음)"
    lines = []
    for line in _read_logcat_lines(path):
        if " am_anr" in line and proc in line:
            lines.append(line.rstrip())
    return "\n".join(lines) if lines else "(am_anr 이벤트 없음)"


# ──────────────────────────────────────────────────────────────────────────────
# [2] ANR in — ActivityManager 섹션
# ──────────────────────────────────────────────────────────────────────────────

def extract_anr_in(path: str) -> str:
    """ActivityManager 로그캣 ANR 블록 추출 (마지막 ANR 기준, TOTAL: 에서 종료)."""

    def _am_content(line):
        m = re.search(r"ActivityManager:\s*(.*)", line)
        return m.group(1).rstrip() if m else None

    last_anr_lineno = -1
    for i, line in enumerate(_read_logcat_lines(path)):
        c = _am_content(line)
        if c and "ANR in " in c:
            last_anr_lineno = i

    if last_anr_lineno == -1:
        return "(ActivityManager ANR 섹션 없음)"

    out = []
    in_cpu_list = False
    cpu_count = 0
    for i, line in enumerate(_read_logcat_lines(path)):
        if i < last_anr_lineno:
            continue
        c = _am_content(line)
        if c is None:
            continue
        if "TOTAL:" in c:
            out.append(c)
            break
        if "CPU usage from" in c:
            in_cpu_list = True
            out.append(c)
            continue
        if in_cpu_list and c and c[0].isdigit():
            cpu_count += 1
            if cpu_count <= 4:
                out.append(c)
            continue
        out.append(c)

    return "\n".join(out) if out else "(ActivityManager ANR 섹션 없음)"


# ──────────────────────────────────────────────────────────────────────────────
# [3] VM TRACES AT LAST ANR
# ──────────────────────────────────────────────────────────────────────────────

def extract_vm_traces(path: str) -> str:
    """VM TRACES: ANR 프로세스 + 관련 프로세스의 main 스레드 +
    락 체인 / 락 경합 / GC 압박 / 컴포넌트 콜백 스레드만 추출."""
    pid, proc = _last_anr_info(path)

    related_pids = set()
    if pid:
        related_pids.add(pid)
    pid_to_cmd = {}

    in_section = False
    pending_pid = None
    for line in _read_lines(path):
        if not in_section:
            if "VM TRACES AT LAST ANR" in line:
                in_section = True
            continue
        if line.startswith("------") and "VM TRACES" not in line:
            break
        m_start = re.match(r"----- pid (\d+) at ", line)
        if m_start:
            pending_pid = m_start.group(1)
            continue
        if pending_pid is not None:
            cm = re.match(r"\s*Cmd line:\s*(\S+)", line)
            if cm:
                cmd_name = cm.group(1)
                pid_to_cmd[pending_pid] = cmd_name
                if proc and (cmd_name == proc or cmd_name.startswith(proc + ":")):
                    related_pids.add(pending_pid)
                pending_pid = None

    if not related_pids:
        return "(VM TRACES AT LAST ANR 섹션 없음)"

    header_line = ""
    blocks_by_pid = {}
    in_section = False
    current_pid = None

    for line in _read_lines(path):
        s = line.rstrip()
        if not in_section:
            if "VM TRACES AT LAST ANR" in line:
                in_section = True
                header_line = s
            continue
        if line.startswith("------") and "VM TRACES" not in line:
            break
        m_start = re.match(r"----- pid (\d+) at ", line)
        if m_start:
            this_pid = m_start.group(1)
            current_pid = this_pid if this_pid in related_pids else None
            continue
        if re.match(r"----- end \d+", line):
            current_pid = None
            continue
        if current_pid is not None:
            if s.startswith("Zygote loaded classes"):
                current_pid = None
                continue
            blocks_by_pid.setdefault(current_pid, []).append(s)

    # CPU 과부하 시 덤프 실패 패턴 두 가지를 모두 감지:
    #   1. libdebuggerd_client: failed  →  tombstoned 타임아웃
    #   2. "sysTid=" 형식 스레드만 있고 Java "tid=" 없음  →  Waiting Channels 폴백
    # 해당 블록은 Waiting Channels / 불완전한 native 프레임만 담고 있어
    # 스택 분석에 쓸 수 없으므로 제거한다.
    failed_dump_pids = set()
    _java_tid_re = re.compile(r'"[^"]*".*\btid=\d+')
    _sys_tid_re  = re.compile(r'"[^"]*".*\bsysTid=\d+')
    for blk_pid, blk_lines in list(blocks_by_pid.items()):
        tombstone_failed = any("libdebuggerd_client: failed" in l for l in blk_lines)
        has_java_tid = any(_java_tid_re.search(l) for l in blk_lines)
        has_sys_tid  = any(_sys_tid_re.search(l) for l in blk_lines)
        if tombstone_failed or (has_sys_tid and not has_java_tid):
            failed_dump_pids.add(blk_pid)
            blocks_by_pid[blk_pid] = []

    def _failed_note(blk_pid):
        cmd = pid_to_cmd.get(blk_pid, "?")
        tag = "[ANR process]" if blk_pid == pid else "[related process]"
        return [
            f"--- {tag} pid {blk_pid}  ({cmd}) ---",
            "",
            "(trace 수집 실패: CPU 과부하로 tombstoned 응답 없음 — 스택 덤프 불가)",
            "",
        ]

    if not any(blocks_by_pid.values()):
        if failed_dump_pids:
            out = [header_line, ""]
            for blk_pid in sorted(failed_dump_pids):
                out += _failed_note(blk_pid)
            return "\n".join(out)
        return "(VM TRACES AT LAST ANR 섹션 없음)"

    def _flush(cur_lines, result, blk_pid):
        if not cur_lines:
            return
        m = re.search(r'"([^"]+)".*\btid=(\d+)', cur_lines[0])
        if not m:
            return
        name, tid = m.group(1), m.group(2)
        waiting_tid = None
        locked_ids, waiting_ids = set(), set()
        for l in cur_lines:
            mw = re.search(r"waiting to lock <([^>]+)>.*held by thread (\d+)", l)
            if mw:
                waiting_ids.add(mw.group(1))
                waiting_tid = mw.group(2)
            ml = re.search(r"- locked <([^>]+)>", l)
            if ml:
                locked_ids.add(ml.group(1))
            mo = re.search(r"- waiting on <([^>]+)>", l)
            if mo:
                waiting_ids.add(mo.group(1))
        result.append({
            'pid': blk_pid, 'name': name, 'tid': tid,
            'waiting_tid': waiting_tid,
            'locked_ids': locked_ids,
            'waiting_ids': waiting_ids,
            'lines': cur_lines,
        })

    all_threads = []
    for blk_pid, blk_lines in blocks_by_pid.items():
        cur = []
        for line in blk_lines:
            if line.startswith('"') and cur:
                _flush(cur, all_threads, blk_pid)
                cur = [line]
            else:
                cur.append(line)
        _flush(cur, all_threads, blk_pid)

    if not all_threads:
        if failed_dump_pids:
            out = [header_line, ""]
            for blk_pid in sorted(failed_dump_pids):
                out += _failed_note(blk_pid)
            return "\n".join(out)
        flat = [l for blk in blocks_by_pid.values() for l in blk]
        return "\n".join([header_line] + flat)

    lock_holder = {}
    for t in all_threads:
        for lid in t['locked_ids']:
            lock_holder[(t['pid'], lid)] = t['tid']

    main_t = next((t for t in all_threads if t['name'] == 'main' and t['pid'] == pid), None)
    if main_t is None:
        main_t = next((t for t in all_threads if t['name'] == 'main'), None)
    if main_t is None:
        if failed_dump_pids:
            out = [header_line, ""]
            for blk_pid in sorted(failed_dump_pids):
                out += _failed_note(blk_pid)
            return "\n".join(out)
        flat = [l for blk in blocks_by_pid.values() for l in blk]
        return "\n".join([header_line] + flat)

    anr_pid = main_t['pid']
    anr_tid_map = {t['tid']: t for t in all_threads if t['pid'] == anr_pid}

    relevant = set()
    queue = [(anr_pid, main_t['tid'])]
    while queue:
        cur_pid, tid = queue.pop(0)
        if (cur_pid, tid) in relevant:
            continue
        relevant.add((cur_pid, tid))
        if cur_pid != anr_pid:
            continue
        t = anr_tid_map.get(tid)
        if not t:
            continue
        if t['waiting_tid'] and (cur_pid, t['waiting_tid']) not in relevant:
            queue.append((cur_pid, t['waiting_tid']))
        for lid in t['waiting_ids']:
            holder = lock_holder.get((cur_pid, lid))
            if holder and (cur_pid, holder) not in relevant:
                queue.append((cur_pid, holder))

    def _is_lock_contention(t_lines):
        header = t_lines[0] if t_lines else ""
        if " Blocked" in header:
            return True
        for l in t_lines:
            if "ConditionObject" in l:
                continue
            if "AbstractQueuedSynchronizer" in l and "acquire" in l:
                return True
            if "BinderProxy.transact" in l:
                return True
            if "monitor contention" in l:
                return True
        return False

    def _is_gc_pressure(t_lines):
        header = t_lines[0] if t_lines else ""
        if "WaitingForGcToComplete" in header:
            return True
        for l in t_lines:
            if "Heap::AllocLargeObject" in l or "Heap::AllocObject" in l:
                return True
            if "art::gc::" in l:
                return True
        return False

    _COMPONENT_HANDLERS = (
        "ActivityThread.handleBindService",
        "ActivityThread.handleCreateService",
        "ActivityThread.handleServiceArgs",
        "ActivityThread.handleReceiver",
        "ActivityThread.installProvider",
        "ActivityThread.installContentProviders",
    )

    def _is_component_callback(t_lines):
        for l in t_lines:
            if any(h in l for h in _COMPONENT_HANDLERS):
                return True
        return False

    for t in all_threads:
        key = (t['pid'], t['tid'])
        if key in relevant:
            continue
        if (_is_lock_contention(t['lines'])
                or _is_gc_pressure(t['lines'])
                or _is_component_callback(t['lines'])):
            relevant.add(key)

    _native_method = re.compile(r'^\s+at .+\(Native [Mm]ethod\)$')
    _native_frame  = re.compile(r'^\s*native:\s+#\d+\s+pc\s')

    out = [header_line, ""]
    pids_ordered = [anr_pid] + [p for p in blocks_by_pid if p != anr_pid]
    for fp in sorted(failed_dump_pids):
        if fp not in pids_ordered:
            pids_ordered.append(fp)
    for blk_pid in pids_ordered:
        if blk_pid in failed_dump_pids:
            out += _failed_note(blk_pid)
            continue
        proc_threads = [
            t for t in all_threads
            if t['pid'] == blk_pid and (t['pid'], t['tid']) in relevant
        ]
        if not proc_threads:
            continue
        cmd = pid_to_cmd.get(blk_pid, "?")
        tag = "[ANR process]" if blk_pid == anr_pid else "[related process]"
        out.append(f"--- {tag} pid {blk_pid}  ({cmd}) ---")
        out.append("")
        for t in proc_threads:
            out.extend(
                l for l in t['lines']
                if not _native_method.match(l) and not _native_frame.match(l)
            )
            out.append("")

    return "\n".join(out)


# ──────────────────────────────────────────────────────────────────────────────
# logcat 태그 추출 및 연속 동일 태그 압축 (공통 유틸)
# ──────────────────────────────────────────────────────────────────────────────
_LOGCAT_TAG_RE = re.compile(
    r"^\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\s+"
    # UID/PID/TID — 각각 숫자 또는 문자열 토큰 (radio, nfc, lmkd 등)
    r"(?:\S+\s+){2,3}"
    r"[VDIWEF]\s+"
    r"(\S+?)\s*:"
)


def _logcat_tag(line: str):
    m = _LOGCAT_TAG_RE.match(line)
    return m.group(1) if m else None


# 그래픽 파이프라인 태그군: 프레임/합성/DVFS 단위로 폭증하며 서로 번갈아 나타난다.
# 개별 줄은 가치가 낮고 "GPU 파이프라인이 폭주했다"는 부하 규모만 중요하므로
# 부하 요약으로 통합 집계한다.
#
# SDHMS / HWUI 도 태그군에 포함하되, GPU hang 을 직접 지목하는 '단서 라인'
# (avgGpuLoad, Davey!) 만은 집계에서 빼고 그대로 보존한다 (_GFX_CLUE_RE).
# 단서 외의 SDHMS PID 잡로그, 일반 HWUI 줄은 폭증 노이즈라 집계로 접는다.
_GRAPHICS_PIPELINE_TAGS = frozenset({
    "SurfaceFlinger", "SurfaceComposerClient", "SurfaceControlRegistry",
    "BLASTBufferQueue", "BLASTBufferQueue_Java",
    "BufferQueue", "BufferQueueProducer", "BufferQueueConsumer", "BufferQueueSource",
    "Layer", "RenderEngine", "GLConsumer", "Gralloc", "GraphicBuffer",
    "VSyncReactor", "VsyncConfiguration", "scheduler",
    "RefreshRateModeManager", "RefreshRateConfigs", "RefreshRateOverlay",
    "DisplayAiqeHalImpl", "NativeSemDvfsManager",
    "SDHMS", "HWUI",
})
_GRAPHICS_GROUP_LABEL = "그래픽 파이프라인"

# GPU hang 단서 — 그래픽 태그라도 이 패턴이 든 줄은 집계하지 않고 보존한다.
# avgGpuLoad/Davey 외에 SDHMS 의 GPU 주파수·제한 신호(GPUFreqMax, GpuLimit 등),
# 써멀 스로틀링/DVFS 의 GPU 클럭 상한 신호(SIOP_GPU, GPUMaxFreq, GPU_FREQ_MAX 등),
# GPU sync 상태(present fence, setStopped) 도 GPU hang 직접 단서라 보존한다.
_GFX_CLUE_RE = re.compile(
    r"avgGpuLoad|Davey|GPUFreqMax|GpuLimit|GpuLoad|isNeedtoGpuLimit"
    r"|SIOP_GPU|GPUMaxFreq|GPU_FREQ_MAX|GPU_MAX_FREQ"
    r"|present fence|Invalid fence|fence signal|setStopped",
    re.IGNORECASE,
)


def _is_graphics_pipeline_line(line: str) -> bool:
    tag = _logcat_tag(line)
    if tag is None or tag not in _GRAPHICS_PIPELINE_TAGS:
        return False
    # 단서 라인은 집계 대상에서 제외 (보존)
    if _GFX_CLUE_RE.search(line):
        return False
    return True


_FRAMENUM_RE = re.compile(r"frameNumber[:=]\s*(\d+)", re.IGNORECASE)


def _aggregate_graphics_pipeline(lines, top_n: int = 3):
    """그래픽 파이프라인 태그 줄을 부하량 요약으로 통합 집계 (옵션 1).

    이벤트 흐름이 아니라 '얼마나 부하가 있었는지'만 LLM 에 전달한다.
    - 태그별 건수 집계.
    - 건수 상위 top_n 태그: 마지막 핵심 줄 1개 + frameNumber 추이(있으면) 표시.
    - 나머지 태그: 건수만 한 줄로.
    프레임 줄은 모두 제거하고 요약 블록을 최초 등장 위치에 삽입한다.
    HWUI(Davey!)/SDHMS 는 태그군에 없어 집계에 걸리지 않고 보존된다."""
    gfx_idx = [i for i, l in enumerate(lines) if _is_graphics_pipeline_line(l)]
    if len(gfx_idx) < 3:
        return lines  # 폭증이 아니면 그대로 둔다.

    def _ts_str(line):
        m = re.match(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
        return m.group(1) if m else "??"

    # 태그별 집계: 건수, 마지막 줄, frameNumber 최소/최대, 시각 범위
    stats = {}  # tag -> {count, last, fmin, fmax, tmin, tmax, tmin_s, tmax_s}
    for i in gfx_idx:
        l = lines[i]
        tag = _logcat_tag(l)
        s = stats.setdefault(tag, {
            "count": 0, "last": l, "fmin": None, "fmax": None,
            "tmin": None, "tmax": None, "tmin_s": None, "tmax_s": None,
        })
        s["count"] += 1
        s["last"] = l
        mf = _FRAMENUM_RE.search(l)
        if mf:
            fn = int(mf.group(1))
            s["fmin"] = fn if s["fmin"] is None else min(s["fmin"], fn)
            s["fmax"] = fn if s["fmax"] is None else max(s["fmax"], fn)
        ts = _logcat_ts(l)
        if ts is not None:
            tstr = _ts_str(l)
            if s["tmin"] is None or ts < s["tmin"]:
                s["tmin"], s["tmin_s"] = ts, tstr
            if s["tmax"] is None or ts > s["tmax"]:
                s["tmax"], s["tmax_s"] = ts, tstr

    total = len(gfx_idx)
    first_ts = _ts_str(lines[gfx_idx[0]])
    last_ts = _ts_str(lines[gfx_idx[-1]])
    ranked = sorted(stats.items(), key=lambda kv: kv[1]["count"], reverse=True)

    block = [
        f"  … [{_GRAPHICS_GROUP_LABEL}] 총 {total}건 "
        f"({first_ts} ~ {last_ts}) — 부하 요약 (흐름 아님)"
    ]
    for tag, s in ranked:
        # frameNumber 추이
        trend = ""
        if s["fmin"] is not None and s["fmax"] is not None:
            trend = f"  frameNumber {s['fmin']}→{s['fmax']} (+{s['fmax'] - s['fmin']})"
        # 지속 시간 + 초당 빈도
        span = ""
        if s["tmin"] is not None and s["tmax"] is not None:
            dur = s["tmax"] - s["tmin"]
            rate = (s["count"] / dur) if dur > 0 else 0.0
            span = (f"  {s['tmin_s'][6:]}~{s['tmax_s'][6:]} "
                    f"({dur:.0f}초간 {s['count']}건, ~{rate:.0f}/s)")
        block.append(f"    {tag} ×{s['count']}{trend}{span}")
        block.append(f"      (마지막) {s['last']}")

    out = []
    inserted = False
    for i, l in enumerate(lines):
        if _is_graphics_pipeline_line(l):
            if not inserted:
                out.extend(block)
                inserted = True
            continue
        out.append(l)
    return out


def _summarize_by_tag(lines, top_n: int = 5, min_total: int = 6):
    """카테고리(4섹션 GC/System/IO 등)를 태그별 부하 요약으로 축약.
    이벤트 흐름이 아니라 '어느 태그가 얼마나 찍혔는지'만 본다.
    - 태그별 건수 집계, 태그별 마지막 줄 1개만 남김.
    - 모든 태그에 대해 마지막 줄 1개를 남김 (시간 기준점 보존).
    - 건수 많은 순으로 정렬.
    - GPU hang 단서 줄(avgGpuLoad/Davey!)은 집계하지 않고 그대로 보존한다.
    - 이미 만들어진 그래픽 요약 블록(들여쓰기 줄)이나 태그 없는 줄도 그대로 통과.
    줄 수가 min_total 미만이면 압축 이득이 없으므로 원본 유지."""
    taggable = [l for l in lines if _logcat_tag(l) is not None]
    if len(taggable) < min_total:
        return lines

    # 통과 줄: 태그 없는 줄(요약 블록 등)은 그대로,
    # GPU 단서 줄(avgGpuLoad/Davey!/GPUFreqMax/SIOP_GPU 등)은
    # (태그, 단서 종류) 단위로 마지막 1줄만 보존한다.
    # (단서 종류는 _GFX_CLUE_RE 가 매칭한 토큰을 소문자로 정규화.
    #  태그 단위로만 dedupe 하면 SDHMS 안의 GPUFreqMax 줄이 SDHMS 의 다른
    #  단서 줄에 덮어써져 사라지는 문제가 있다.)
    plain_passthrough = [l for l in lines if _logcat_tag(l) is None]
    clue_last = {}   # (tag, kind) -> 마지막 줄
    clue_count = {}  # (tag, kind) -> 건수
    for l in lines:
        if _logcat_tag(l) is None:
            continue
        m = _GFX_CLUE_RE.search(l)
        if not m:
            continue
        tag = _logcat_tag(l)
        kind = m.group(0).lower()
        key = (tag, kind)
        clue_last[key] = l
        clue_count[key] = clue_count.get(key, 0) + 1

    stats = {}  # tag -> {"count", "last"}
    for l in lines:
        tag = _logcat_tag(l)
        if tag is None or _GFX_CLUE_RE.search(l):
            continue  # 단서 줄은 집계에서 제외 (보존)
        if tag not in stats:
            stats[tag] = {"count": 0, "last": l}
        stats[tag]["count"] += 1
        stats[tag]["last"] = l

    ranked = sorted(stats.items(), key=lambda kv: kv[1]["count"], reverse=True)
    out = list(plain_passthrough)  # 요약 블록 등 통과
    # GPU 단서 먼저(눈에 띄게): (태그, 단서 종류) 단위로 마지막 줄 + 건수
    for (tag, kind), last in clue_last.items():
        cnt = clue_count[(tag, kind)]
        suffix = f"  ({kind} ×{cnt})" if cnt > 1 else f"  ({kind})"
        out.append(f"    [GPU 단서]{suffix}")
        out.append(f"      {last}")
    for tag, s in ranked:
        out.append(f"    {tag} ×{s['count']}")
        out.append(f"      (마지막) {s['last']}")
    return out


def _tag_group(tag: str) -> str:
    if "." in tag:
        return tag.split(".", 1)[0] + ".*"
    return tag


def _collapse_consecutive_same_tag(lines, keep_head: int = 1):
    """같은 태그 그룹 연속 구간 압축. 앞 1줄 + 압축 표시 + 마지막 1줄."""
    if not lines:
        return lines
    out = []
    i, n = 0, len(lines)
    while i < n:
        tag_i = _logcat_tag(lines[i])
        if tag_i is None:
            out.append(lines[i])
            i += 1
            continue
        group_i = _tag_group(tag_i)
        j = i + 1
        while j < n:
            tag_j = _logcat_tag(lines[j])
            if tag_j is None or _tag_group(tag_j) != group_i:
                break
            j += 1
        run = lines[i:j]
        if len(run) >= keep_head + 2:
            out.extend(run[:keep_head])
            collapsed = len(run) - keep_head - 1
            out.append(f"  … [{group_i}] × {collapsed}건 압축")
            out.append(run[-1])
        else:
            out.extend(run)
        i = j
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 거대 단일 라인 절단 (TaskInfo / TransitionRequestInfo 등 객체 dump 폭증 차단)
# ──────────────────────────────────────────────────────────────────────────────
#
# Android 시스템 로그는 한 줄에 객체 전체를 직렬화해 박는 경우가 많다
# (WindowManagerShell, InsetsController, WindowManager 등이 상습).
# ANR 분석에는 앞부분만 있어도 충분하므로 라인 단위로 잘라서 토큰을 절약한다.
#
# 측정 사례 (GC 폭주 케이스):
#   [5] freeze 이전 로그 1,155 라인 중 30 라인이 2,000자 초과,
#   이 30 라인이 [5] 전체의 27.9% (86k chars) 차지.
#   500자로 자르면 [5] 가 312k → 약 200k 로 감소 (≈ 35% 절약).
_MAX_LINE_LEN_DEFAULT = 500


def _truncate_long_lines(lines, max_len: int = _MAX_LINE_LEN_DEFAULT):
    """각 라인을 max_len 자로 잘라 절약. 잘린 분량을 표시한다."""
    out = []
    for l in lines:
        if len(l) <= max_len:
            out.append(l)
        else:
            cut = len(l) - max_len
            out.append(l[:max_len] + f" … (+{cut:,}자 절단)")
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 사전 패키지 로그 ([5]) 노이즈 태그 필터링
# ──────────────────────────────────────────────────────────────────────────────
#
# 4 케이스(락 데드락 / ReentrantLock 대기 / synchronized 락 보유 지연 / GC 압박)
# 교차 검증 결과 일관되게 무관한 태그 집합. 평균 60% 이상 노이즈 제거 효과.
# 새 OEM 노이즈 태그가 발견되면 여기에 추가한다.
_DROP_TAGS_PRE_FREEZE = {
    # 그래픽 / Surface 파이프라인 (4 케이스 평균 23% 점유)
    # HWUI 는 Davey! 만 살려야 해서 별도 메시지 패턴으로 처리 (아래 _HWUI_KEEP_PATTERN)
    "SurfaceFlinger", "SurfaceComposerClient", "SurfaceControlRegistry",
    "Layer", "RenderEngine", "BufferQueue",

    # Insets 상태 변화 (평균 8.5%)
    "InsetsSourceProvider", "InsetsController", "InsetsSourceConsumer",
    "InsetsPolicy",

    # 트랜지션 내부 디테일 (평균 8%)
    "ChangeTransitionController", "TaskOrganizerController",
    "WindowManagerShell",

    # 패키지 가시성 정책 (평균 2.7%)
    "AppsFilter",

    # IME 트래커 / Back 제스처 (작지만 일관되게 무관)
    "ImeTracker", "CoreBackPreview",

    # 그래픽/네이티브 로더 초기화
    "nativeloader", "GraphicsEnvironment",

    # 삼성 OEM 모듈 (다른 OEM 단말에선 다른 태그가 나올 수 있음)
    # SDHMS 는 PID/온도/GPU 스로틀링 시그널이 필요해서 의도적으로 제외
    # (wallpaper GPU 과점 → 카메라 ANR 같은 케이스에서 avgGpuLoad/Target Temp 등 단서)
    "SGM",  # 게임매니저
    "SAMSUNGWALLET",
    "HBD",
    "MdnieScenarioControlService",  # 디스플레이 색감
    "SecSTQuickControlRequestReceiver",
    "PersonaActivityHelper",
    "EMMAgent",
    "Navbar.Store", "NavigationBar",
    "NowBarExternalViewCardView",  # Now Bar 카드 뷰

    # 진동 및 알림 관련 (단순 UI/UX 피드백)
    "VibratorManagerService", "VibrationThread",
    "NotificationManager", "NotificationReminder", "NotifHistoryProto",
    "EdgeLightingManager", "EdgeLightingPolicyManager",

    # 시스템 설정 및 권한 확인 (단순 조회)
    "PackageConfigPersister", "AppOps", "Settings",

    # 백그라운드 최적화 및 기타 잡로그
    "FreecessHandler", "Pageboost",
    "[secipm]", "secipm",  # 표시 형식 양쪽 모두 대응
}

# WindowManager 는 평균 24% 로 가장 비대하지만 중요한 사건도 포함
# (focus 변경, WIN DEATH 등). 메시지 패턴으로 분류해서 의미 있는 것만 유지.
_WM_KEEP_PATTERN = re.compile(
    r"Changing focus|"
    r"WIN DEATH|WINDOW DIED|Window died|"
    r"Force removing|app died|"
    r"finishDrawingWindow|removeWindowToken|onRemovedFromDisplay"
)

# HWUI 는 보통 노이즈지만 Davey! (프레임 1500ms+ 지연 시그널) 은 매우 중요.
# UI 스레드가 오래 멈췄다는 직접 증거라서 ANR 분석의 핵심 단서가 된다.
_HWUI_KEEP_PATTERN = re.compile(r"Davey")

# HoneySpace.* 형식의 삼성 런처 관련 태그를 한 번에 걸러내기 위한 prefix 매칭
_DROP_TAG_PREFIXES = (
    "HoneySpace.",  # 삼성 OneUI 런처
)


def _should_drop_pre_freeze(tag: str, message: str) -> bool:
    """[5] 로그 라인을 버려야 하면 True."""
    if tag in _DROP_TAGS_PRE_FREEZE:
        return True
    for prefix in _DROP_TAG_PREFIXES:
        if tag.startswith(prefix):
            return True
    # WindowManager 는 메시지 패턴으로 추가 필터
    if tag == "WindowManager":
        if not _WM_KEEP_PATTERN.search(message):
            return True
    # HWUI 는 Davey! 같은 jank 시그널만 유지하고 나머지는 버린다
    if tag == "HWUI":
        if not _HWUI_KEEP_PATTERN.search(message):
            return True
    return False


def _filter_pre_freeze_tags(lines):
    """[5] 의 노이즈 태그 라인 제거. (남은 라인, 제거된 건수) 반환."""
    out = []
    dropped = 0
    for l in lines:
        m = _LOGCAT_TAG_RE.match(l)
        if m:
            tag = m.group(1)
            # 메시지 부분 (태그 ':' 뒤)
            msg = l[m.end():] if m.end() < len(l) else ""
            if _should_drop_pre_freeze(tag, msg):
                dropped += 1
                continue
        out.append(l)
    return out, dropped


# ──────────────────────────────────────────────────────────────────────────────
# [4] ANR 발생 시점 부근 logcat 키워드
# ──────────────────────────────────────────────────────────────────────────────
_GC_KW = [
    "WaitForGcToComplete blocked", "Starting a blocking GC",
    "Throwing OutOfMemoryError", "Clamp target GC heap",
    "Forcing collection of SoftReferences", "GC_FOR_ALLOC",
    "GC concurrent", "Explicit concurrent mark sweep GC",
    "Background concurrent copying GC", "Suspending all threads",
    "OutOfMemoryError", "Failed to allocate", "Trim memory",
]
_SYSTEM_KW = [
    "lowmemorykiller", "lmkd", "Kill '", "freeze ", "unfreeze ",
    "Freezer", "cpu starvation", "task stalled", "hung task",
    "sched_blocked", "sched delay", "schedule delay", "scheduling latency",
    "Slow main thread", "Slow Looper", "Slow dispatch", "Slow delivery",
    "watchdog", "WATCHDOG",
    "dvm_lock_sample",  # 락 경합 직접 시그널 (dalvik: 임계 이상 락 대기 시 기록)
]
_RENDER_KW = [
    "SurfaceFlinger", "BufferQueue", "dequeueBuffer", "queueBuffer",
    "EGL", "OpenGLRenderer", "HWUI", "FrameMissed", "jank", "RenderThread",
    "Davey!", "avgGpuLoad", "BLASTBufferQueue",
    "Skipped frames",   # main thread 블로킹 부산물 (Choreographer)
    "setStopped",       # HardwareRenderer 블로킹 지점
    "present fence",    # GPU sync 상태
]
_IO_KW = [
    "I/O error", "Slow operation", "fsync", "storage", "SQLite",
    "database is locked", "disk full", "read blocked", "write blocked",
]

# 카테고리별 키워드를 미리 하나의 정규식으로 컴파일.
# 127만 줄 × for kw in kws 루프 → 127만 줄 × re.search(C레벨) 1회로 교체.
# 결과(어떤 줄이 매칭되는지)는 완전히 동일하고 속도만 개선된다.
def _kw_re(kws):
    return re.compile("|".join(re.escape(k) for k in kws))

_GC_RE     = _kw_re(_GC_KW)
_SYSTEM_RE = _kw_re(_SYSTEM_KW)
_RENDER_RE = _kw_re(_RENDER_KW)
_IO_RE     = _kw_re(_IO_KW)


def extract_logcat_window(path: str, window_before: int = 180) -> str:
    """ANR 시점 기준 logcat 에서 GC/System/Render/IO 키워드 수집.
    카테고리별 부하 요약. ANR 이전 구간만 본다 (ANR 이후는 노이즈라 제외)."""
    anr_ts = None
    for line in _read_logcat_lines(path):
        if " am_anr" in line:
            ts = _logcat_ts(line)
            if ts is not None:
                anr_ts = ts

    t_start = (anr_ts - window_before) if anr_ts else None
    t_end   = anr_ts  # ANR 시점까지만

    found = {"GC": [], "System": [], "Render": [], "IO": []}
    cat_res = {"GC": _GC_RE, "System": _SYSTEM_RE, "Render": _RENDER_RE, "IO": _IO_RE}
    MAX = 20000
    in_window = (anr_ts is None)

    # 주의: dumpstate 는 EVENT/SYSTEM/MAIN 등 여러 logcat 버퍼를 이어 붙여서,
    # 파일을 순차로 읽으면 버퍼 경계에서 시간이 되감겼다 다시 흐른다.
    # 따라서 "시각이 윈도우를 지났다"고 break 하면 뒤 버퍼(예: SYSTEM LOG)의
    # 로그를 통째로 놓친다. 시간 기반 break 를 쓰지 않고 전체를 훑되,
    # 윈도우 필터로만 거른다. 폭주 방지는 카테고리별 MAX 로 한다.
    for line in _read_logcat_lines(path):
        if all(len(v) >= MAX for v in found.values()):
            break
        # 타임스탬프가 아예 없는 줄(헤더, 멀티라인 등)은 빠르게 skip.
        if anr_ts is not None and not line[:2].isdigit():
            continue
        ts = None
        if anr_ts is not None:
            ts = _logcat_ts(line)
            if ts is not None:
                in_window = (t_start <= ts <= t_end)
        if not in_window:
            continue
        # 윈도우 안에서만 비싼 정규식 검사 수행.
        is_clue = bool(_GFX_CLUE_RE.search(line))
        for cat, cat_re in cat_res.items():
            # MAX 가드. GPU 단서는 그래픽 폭증으로 Render 가 MAX 에 도달해도 통과.
            if len(found[cat]) >= MAX and not (is_clue and cat == "Render"):
                continue
            # GPU 단서 줄은 Render 키워드에 안 걸려도(예: [GPUFreqMax]) Render 로 수집.
            if is_clue and cat == "Render":
                found[cat].append(line.rstrip())
                continue
            if cat_re.search(line):
                found[cat].append(line.rstrip())

    parts = []
    if anr_ts is not None:
        parts.append(f"(스캔: ANR-{window_before}s ~ ANR 시점)")
    else:
        parts.append("(am_anr 이벤트 미발견 — 파일 전체 스캔)")

    has_any = False
    for cat, lines in found.items():
        if lines:
            has_any = True
            parts.append(f"\n[{cat}]")
            if cat == "Render":
                # 그래픽 폭증을 frameNumber 추이 + 단서 보존으로 먼저 접고,
                lines = _aggregate_graphics_pipeline(lines)
            # 모든 카테고리를 태그별 부하 요약으로 축약 (흐름 아님, 부하량만).
            lines = _summarize_by_tag(lines)
            parts.extend(_truncate_long_lines(lines))

    if not has_any:
        parts.append("(해당 키워드 없음)")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# [5] ANR-3분 ~ ANR 시점 ANR 패키지 로그
# ──────────────────────────────────────────────────────────────────────────────

def extract_pre_freeze_log(path: str, lookback: int = 180, compress: bool = True) -> str:
    """ANR 시점 기준 lookback초 전부터 ANR 시점까지 ANR 패키지 로그 추출.
    compress=True(기본): 태그별 부하 요약 (토큰 절약).
    compress=False (-nc5 플래그): 연속 동일 태그 압축만 적용 — 시간 흐름 보존."""
    pid, proc = _last_anr_info(path)
    if proc is None:
        return "(ANR 프로세스 정보 없음)"

    anr_ts = None
    anr_time_str = ""
    delay_ms = 0
    for line in _read_logcat_lines(path):
        if " am_anr" not in line or proc not in line:
            continue
        ts = _logcat_ts(line)
        if ts is not None:
            anr_ts = ts
            m_ts = re.match(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
            if m_ts:
                anr_time_str = m_ts.group(1)
        m_d = re.search(r"Waited (\d+)ms", line)
        if m_d:
            delay_ms = int(m_d.group(1))

    if anr_ts is None:
        return "(ANR 타임스탬프 추출 실패)"

    t_start = anr_ts - lookback
    t_end   = anr_ts

    out_lines = []
    for line in _read_logcat_lines(path):
        ts = _logcat_ts(line)
        if ts is None:
            continue
        # dumpstate 다중 버퍼(시간 되감김) 때문에 시간 기반 break 금지.
        if t_start <= ts <= t_end and proc in line:
            out_lines.append(line.rstrip())

    raw_count = len(out_lines)
    out_lines, dropped = _filter_pre_freeze_tags(out_lines)
    out_lines = _aggregate_graphics_pipeline(out_lines)
    if compress:
        out_lines = _summarize_by_tag(out_lines)
    else:
        out_lines = _collapse_consecutive_same_tag(out_lines)
    out_lines = _truncate_long_lines(out_lines)

    mode_str = "태그별 요약" if compress else "시간순 (-nc5)"
    delay_note = f"  /  ANR 지연: {delay_ms}ms" if delay_ms else ""
    header = (
        f"(ANR 시각: {anr_time_str}{delay_note}  /  "
        f"스캔 범위: ANR-{lookback}s ~ ANR 시점  /  "
        f"매칭: 패키지명 '{proc}' 포함  /  "
        f"원본 {raw_count}건 → 노이즈 태그 {dropped}건 필터링됨  /  {mode_str})"
    )
    if not out_lines:
        return f"{header}\n({proc} 관련 로그 없음)"
    return header + "\n" + "\n".join(out_lines)


# ──────────────────────────────────────────────────────────────────────────────
# 키워드 2차 분석 — 덤프 전체에서 특정 키워드 포함 라인 추출
# ──────────────────────────────────────────────────────────────────────────────

def extract_keyword_lines(path, keywords, lookback: int = 180):
    """[5] 1차 분석과 동일한 윈도우/압축/절단을 키워드 매칭으로 수행 (2차 분석).
    노이즈 필터는 미적용 — 키워드 지정은 사용자가 그 줄을 보겠다는 의도이므로
    SurfaceFlinger 등 필터 대상 태그도 키워드로 명시하면 그대로 나온다."""
    anr_ts = None
    anr_time_str = ""
    delay_ms = 0
    for line in _read_logcat_lines(path):
        if " am_anr" not in line:
            continue
        ts = _logcat_ts(line)
        if ts is not None:
            anr_ts = ts
            m_ts = re.match(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
            if m_ts:
                anr_time_str = m_ts.group(1)
        m_d = re.search(r"Waited (\d+)ms", line)
        if m_d:
            delay_ms = int(m_d.group(1))

    if anr_ts is None:
        return "(ANR 타임스탬프 추출 실패 — am_anr 이벤트 없음)"

    t_start = anr_ts - lookback
    t_end   = anr_ts
    kws_lower = [k.lower() for k in keywords]

    matched = []
    for line in _read_logcat_lines(path):
        ts = _logcat_ts(line)
        if ts is None:
            continue
        # dumpstate 다중 버퍼(시간 되감김) 때문에 시간 기반 break 금지.
        if t_start <= ts <= t_end:
            low = line.lower()
            if any(k in low for k in kws_lower):
                matched.append(line.rstrip())

    raw_count = len(matched)
    # 노이즈 필터·압축 미적용: 키워드 지정은 사용자가 원본 줄을 보겠다는 의도.
    matched = _truncate_long_lines(matched)

    delay_note = f"  /  ANR 지연: {delay_ms}ms" if delay_ms else ""
    header = (
        f"(ANR 시각: {anr_time_str}{delay_note}  /  "
        f"스캔 범위: ANR-{lookback}s ~ ANR 시점  /  "
        f"키워드: {', '.join(keywords)} (대소문자 무시)  /  "
        f"원본 {raw_count}건  /  노이즈 필터·압축 미적용)"
    )
    if not matched:
        return f"{header}\n(매칭 라인 없음)"
    return header + "\n" + "\n".join(matched)


# ──────────────────────────────────────────────────────────────────────────────
# [6] Crash 기록 — Java crash + native crash + TOMBSTONE 섹션
# ──────────────────────────────────────────────────────────────────────────────

_JAVA_TRACE_CONT = re.compile(
    r"^\s*(at\s+\S|Caused by:|\.{3}\s+\d+\s+more|Suppressed:|"
    r"\$?[A-Za-z_][\w.$]*(Exception|Error|Throwable):)"
)


def _rel_to_anr(ts, anr_ts):
    if ts is None or anr_ts is None:
        return ""
    d = ts - anr_ts
    sign = "+" if d >= 0 else "-"
    return f" (ANR Δ {sign}{abs(d):.1f}s)"


def _extract_java_crashes(path, anr_ts):
    out = []
    lines = _read_lines(path)
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if "FATAL EXCEPTION" not in line:
            i += 1
            continue
        ts = _logcat_ts(line)
        m_t = re.match(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
        tstr = m_t.group(1) if m_t else "??"
        lineno = i + 1
        block = [line.rstrip()]
        proc = "?"
        j = i + 1
        blank_run = 0
        while j < n:
            nxt = lines[j]
            mb = re.search(r"\bE\s+\S+\s*:\s*(.*)$", nxt)
            content = mb.group(1) if mb else nxt.strip()
            if proc == "?":
                mp = re.search(r"Process:\s*([\w.]+)", nxt)
                if mp:
                    proc = mp.group(1)
            if ("Process:" in nxt or "PID:" in nxt
                    or _JAVA_TRACE_CONT.match(content)
                    or content == ""):
                if content == "":
                    blank_run += 1
                    if blank_run >= 2:
                        break
                else:
                    blank_run = 0
                block.append(nxt.rstrip())
                j += 1
            else:
                break
        out.append((ts, tstr, "JAVA", block, lineno, proc))
        i = j
    return out


def _extract_native_crashes(path, anr_ts):
    out = []
    lines = _read_lines(path)
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if "Fatal signal" not in line and "*** *** *** ***" not in line:
            i += 1
            continue
        ts = _logcat_ts(line)
        m_t = re.match(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
        tstr = m_t.group(1) if m_t else "??"
        lineno = i + 1
        block = []
        proc = "?"
        j = i
        unrelated = 0
        while j < n and len(block) < 80:
            cur = lines[j]
            if cur.lstrip().startswith("------"):
                break
            if re.search(
                r"Fatal signal|signal \d+ \(SIG|Abort message|backtrace:|"
                r"#\d{2} pc |\*\*\* \*\*\*|pid: \d+, tid: \d+|"
                r"name: .*>>> .* <<<|libc :|DEBUG\s*:", cur
            ):
                block.append(cur.rstrip())
                unrelated = 0
                if proc == "?":
                    mp = (re.search(r">>>\s*([\w./:]+)\s*<<<", cur)
                          or re.search(r"\bname:\s*(\S+)", cur))
                    if mp:
                        proc = mp.group(1)
            else:
                unrelated += 1
                if unrelated >= 8:
                    break
            j += 1
        if block:
            out.append((ts, tstr, "NATIVE", block, lineno, proc))
        i = max(j, i + 1)
    return out


def _extract_tombstones(path):
    out = []
    lines = _read_lines(path)
    i, n = 0, len(lines)
    while i < n:
        if "TOMBSTONE" not in lines[i] or not lines[i].lstrip().startswith("---"):
            i += 1
            continue
        lineno = i + 1
        j = i + 1
        block = []
        proc = "?"
        kept = 0
        while j < n:
            cur = lines[j]
            if cur.lstrip().startswith("------") and "TOMBSTONE" not in cur:
                break
            if re.search(
                r"signal \d+ \(SIG|Abort message|pid: \d+, tid: \d+|"
                r"name: |>>> .* <<<|#\d{2} pc |Cmdline:|"
                r"Build fingerprint|Revision:|ABI:", cur
            ):
                block.append(cur.rstrip())
                kept += 1
                if proc == "?":
                    mp = (re.search(r"Cmdline:\s*(\S+)", cur)
                          or re.search(r">>>\s*([\w./:]+)\s*<<<", cur)
                          or re.search(r"\bname:\s*(\S+)", cur))
                    if mp:
                        proc = mp.group(1)
                if kept >= 60:
                    block.append("      … (backtrace 이하 생략)")
                    break
            j += 1
        if block:
            out.append((None, "(tombstone 섹션)", "TOMBSTONE", block, lineno, proc))
        i = max(j, i + 1)
    return out


def extract_crash_records(path: str) -> str:
    """파일 전체에서 Java/native crash + TOMBSTONE 을 모두 수집."""
    anr_ts = None
    for line in _read_logcat_lines(path):
        if " am_anr" in line:
            t = _logcat_ts(line)
            if t is not None:
                anr_ts = t
    _, anr_proc = _last_anr_info(path)

    crashes = []
    try:
        crashes += _extract_java_crashes(path, anr_ts)
    except Exception as e:
        crashes.append((None, "??", "JAVA", [f"(Java crash 추출 오류: {e})"], 0, "?"))
    try:
        crashes += _extract_native_crashes(path, anr_ts)
    except Exception as e:
        crashes.append((None, "??", "NATIVE", [f"(native crash 추출 오류: {e})"], 0, "?"))
    try:
        crashes += _extract_tombstones(path)
    except Exception as e:
        crashes.append((None, "??", "TOMBSTONE", [f"(tombstone 추출 오류: {e})"], 0, "?"))

    if not crashes:
        return "(Crash 기록 없음 — FATAL EXCEPTION / Fatal signal / TOMBSTONE 미발견)"

    crashes.sort(key=lambda c: (c[0] is None, c[0] if c[0] is not None else 0))

    def selection_key(c):
        ts = c[0]
        if ts is None or anr_ts is None:
            return (1, 0)
        return (0, abs(ts - anr_ts))

    def is_anr_pkg(c):
        return anr_proc is not None and anr_proc in (c[5] or "")

    anr_related = [c for c in crashes if is_anr_pkg(c)]
    if anr_related:
        representative = min(anr_related, key=selection_key)
        sel_reason = f"ANR 패키지({anr_proc}) 관련 중 ANR 시각에 가장 근접"
    else:
        representative = min(crashes, key=selection_key)
        sel_reason = "ANR 패키지 관련 crash 없음 → 전체 중 ANR 시각에 가장 근접"

    parts = [
        f"(총 {len(crashes)}건 발견 — 파일 전체 스캔)",
        f"대표 선정 기준: {sel_reason}",
        "",
        "─── 대표 Crash (상세) ───",
    ]
    rep_ts, rep_tstr, rep_kind, rep_block, rep_lineno, rep_proc = representative
    rel = _rel_to_anr(rep_ts, anr_ts)
    parts.append(f"[{rep_kind}]  {rep_tstr}{rel}  proc={rep_proc}  @ line {rep_lineno}")
    parts.extend(rep_block)

    others = [c for c in crashes if c is not representative]
    if others:
        parts.append("")
        parts.append(f"─── 기타 Crash 인덱스 ({len(others)}건, 상세는 원본 파일 참조) ───")
        for c in others:
            ts, tstr, kind, _, lineno, proc = c
            rel = _rel_to_anr(ts, anr_ts)
            parts.append(f"  [{kind:<9s}] {tstr}{rel}  proc={proc}  @ line {lineno}")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# 파싱 실행 및 저장
# ──────────────────────────────────────────────────────────────────────────────

# 분석용 — _anr_parsed.txt 에 저장됨 (LLM 이 읽는 파일)
SECTIONS_MAIN = [
    ("[1] am_anr 이벤트",                          extract_am_anr),
    ("[2] ANR in  (ActivityManager 섹션)",          extract_anr_in),
    ("[3] VM TRACES AT LAST ANR  (스레드 덤프)",   extract_vm_traces),
    ("[4] ANR 부근 logcat 키워드  (ANR-180s ~ ANR 시점)",  extract_logcat_window),
    ("[5] ANR-3분 로그  (패키지명 기준, ANR-180s ~ ANR)", extract_pre_freeze_log),
]

# 참고용 — _anr_crashes.txt 에 별도 저장됨 (ANR 분석에 사용하지 않음)
SECTIONS_AUX = [
    ("[A] Crash 기록  (Java / native / TOMBSTONE, 파일 전체)", extract_crash_records),
]

SEP = "=" * 80


def _write_sections(dumpstate_path: str, sections, header_title: str, out_path: str):
    """주어진 섹션들을 실행하여 결과를 파일로 저장."""
    output_lines = [
        header_title,
        f"파서 버전 : {__version__}",
        f"원본 : {os.path.basename(dumpstate_path)}",
        f"일시 : {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}",
        SEP,
    ]
    for title, fn in sections:
        output_lines += [f"\n{SEP}", title, SEP]
        try:
            output_lines.append(fn(dumpstate_path))
        except Exception as e:
            output_lines.append(f"(오류: {e})")
        print(f"  ✓ {title}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


def parse_and_save(dumpstate_path: str, compress_5: bool = True,
                   keywords: list = None) -> Optional[str]:
    dumpstate_path = dumpstate_path.strip().strip('"').strip("'")
    if not os.path.isfile(dumpstate_path):
        print(f"  ⚠ 파일을 찾을 수 없습니다: {dumpstate_path}")
        return None

    print(f"\n파싱 중: {os.path.basename(dumpstate_path)}")
    if not compress_5:
        print("  [5] 섹션 압축 해제 (-nc5)")
    if keywords:
        print(f"  키워드 섹션 추가: {', '.join(keywords)}")

    base = os.path.splitext(dumpstate_path)[0]
    main_path = base + "_anr_parsed.txt"
    aux_path  = base + "_anr_crashes.txt"

    # 5섹션만 compress_5 플래그를 받아 동적으로 생성
    sec5_label = "[5] ANR-3분 로그  (패키지명 기준, ANR-180s ~ ANR)"
    sec5_fn = (lambda p: extract_pre_freeze_log(p, compress=compress_5))
    sections_main = SECTIONS_MAIN[:-1] + [(sec5_label, sec5_fn)]

    # 1. 분석용 메인 출력 (LLM 이 읽음)
    _write_sections(
        dumpstate_path,
        sections_main,
        "ANR 파싱 결과 (분석용)",
        main_path,
    )

    # 키워드 섹션이 있으면 _anr_parsed.txt 뒤에 붙임
    if keywords:
        with open(main_path, "a", encoding="utf-8") as f:
            for kw in keywords:
                f.write(f"\n{SEP}\n[K] 키워드: {kw}\n{SEP}\n")
                try:
                    f.write(extract_keyword_lines(dumpstate_path, [kw]))
                except Exception as e:
                    f.write(f"(오류: {e})")
                f.write("\n")
                print(f"  ✓ [K] 키워드: {kw}")

    # 2. 참고용 부록 출력 (사용자 참고용 — LLM 은 읽지 않음)
    _write_sections(
        dumpstate_path,
        SECTIONS_AUX,
        "ANR 부록 — Crash 기록 (참고용 · ANR 분석에 사용되지 않음)",
        aux_path,
    )

    print(f"\n  → 분석용 저장: {main_path}")
    print(f"  → 부록 저장  : {aux_path}")
    # 이 덤프 처리가 끝나면 라인 캐시를 비워 메모리를 회수한다 (interactive 모드 대비).
    _LINE_CACHE.clear()
    return main_path


def keyword_search_and_save(dumpstate_path, keywords):
    """키워드 2차 분석 결과를 <원본>_anr_keyword_<키워드>.txt 로 저장."""
    dumpstate_path = dumpstate_path.strip().strip('"').strip("'")
    if not os.path.isfile(dumpstate_path):
        print(f"  ⚠ 파일을 찾을 수 없습니다: {dumpstate_path}")
        return None

    print(f"\n키워드 파싱 중: {os.path.basename(dumpstate_path)}"
          f"  (키워드: {', '.join(keywords)})")

    base = os.path.splitext(dumpstate_path)[0]
    slug = "_".join(re.sub(r"[^\w.-]", "", k) for k in keywords) or "kw"
    out_path = f"{base}_anr_keyword_{slug}.txt"

    body = extract_keyword_lines(dumpstate_path, keywords)
    output_lines = [
        "ANR 키워드 추가 분석",
        f"파서 버전 : {__version__}",
        f"원본 : {os.path.basename(dumpstate_path)}",
        f"키워드 : {', '.join(keywords)}",
        f"일시 : {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}",
        SEP,
        "",
        body,
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print("  ✓ 키워드 추출 완료")
    print(f"\n  → 키워드 결과 저장: {out_path}")
    return out_path


def _parse_args(args):
    """sys.argv 파싱. (path, keywords, compress_5) 반환.
    경로에 공백이 있어도 따옴표 없이 받을 수 있도록 플래그 외 토큰은 합친다.
    -nc5         : 5섹션 압축 해제 — 태그별 요약 대신 시간순 연속 압축 사용.
    -k a b c     : 여러 키워드를 한 번에 지정 (공백 구분). 다음 플래그(-로 시작)까지가 키워드.
    -k a -k b    : 기존 형식도 그대로 지원."""
    keywords = []
    path_parts = []
    compress_5 = True
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-k", "--keyword"):
            i += 1
            # 다음 플래그(-로 시작)가 나올 때까지 키워드로 수집
            while i < len(args) and not args[i].startswith("-"):
                keywords.append(args[i]); i += 1
        elif a == "-nc5":
            compress_5 = False; i += 1
        else:
            path_parts.append(a); i += 1
    return " ".join(path_parts), keywords, compress_5


def main():
    if len(sys.argv) > 1:
        path, keywords, compress_5 = _parse_args(sys.argv[1:])
        parse_and_save(path, compress_5=compress_5, keywords=keywords)
        return

    print("=" * 50)
    print(f"ANR dumpstate 파서  v{__version__}")
    print("dumpstate 파일을 드래그하거나 경로를 입력하세요.")
    print("플래그: -k <키워드>  /  -nc5 (5섹션 압축 해제)")
    print("종료: exit")
    print("=" * 50)

    while True:
        try:
            raw = input("\n경로 입력 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break
        if not raw or raw.lower() in ("exit", "quit"):
            break
        path_interactive, keywords_interactive, compress_5 = _parse_args(raw.split())
        parse_and_save(path_interactive, compress_5=compress_5, keywords=keywords_interactive)


if __name__ == "__main__":
    main()
