#!/usr/bin/env python3
"""
anr_parse.py
dumpstate 파일에서 ANR 관련 4개 섹션을 추출해 텍스트 파일로 저장.

사용법:
  python anr_parse.py <dumpstate_path>
  또는 실행 후 경로 드래그/입력

출력 섹션:
  [1] am_anr       — logcat am_anr 이벤트
  [2] ANR in       — ActivityManager ANR 헤더 + CPU 사용량 + PSI 메모리
  [3] VM traces    — VM TRACES AT LAST ANR 스레드 덤프
  [4] 부근 logcat  — ANR 발생 시점 -120s ~ +10s 키워드 (GC / System / Render / IO)

외부 라이브러리 불필요 (표준 라이브러리만 사용).
"""

import os
import re
import sys
from datetime import datetime as _dt


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
    """마지막 am_anr 이벤트에서 (pid, process_name) 반환. 없으면 (None, None).
    am_anr 포맷: [user_id,pid,process_name,flags,reason]
    """
    pid, proc = None, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
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
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
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

    # 1단계: 마지막 "ANR in" 라인 번호 탐색 (ActivityManager 태그 필수)
    last_anr_lineno = -1
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            c = _am_content(line)
            if c and "ANR in " in c:
                last_anr_lineno = i

    if last_anr_lineno == -1:
        return "(ActivityManager ANR 섹션 없음)"

    # 2단계: 마지막 "ANR in"부터 첫 번째 TOTAL: 까지 AM 태그 라인만 수집
    # CPU 프로세스 항목(들여쓰기로 시작하는 줄)은 상위 4개까지만 포함
    out = []
    in_cpu_list = False
    cpu_count = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
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
            if in_cpu_list and c and c[0].isdigit():  # 숫자로 시작 = CPU 프로세스 항목
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
    """VM TRACES: ANR 프로세스 + 관련(같은 패키지) 프로세스의 main 스레드 +
    락 체인 / 락 경합 / GC 압박 / 컴포넌트 콜백 스레드만 추출."""
    pid, proc = _last_anr_info(path)

    # ── 1. 관련 pid 식별 (Cmd line이 packageName으로 시작) ───────────
    related_pids = set()
    if pid:
        related_pids.add(pid)
    pid_to_cmd = {}  # pid → Cmd line (출력 헤더용)

    in_section = False
    pending_pid = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
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

    # ── 2. 관련 pid 블록 모두 수집 ─────────────────────────────────────
    header_line = ""
    blocks_by_pid = {}  # pid → list of lines (해당 블록)
    in_section = False
    current_pid = None

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
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
                    current_pid = None  # 이 블록의 ART 통계 이후는 버림
                    continue
                blocks_by_pid.setdefault(current_pid, []).append(s)

    if not any(blocks_by_pid.values()):
        return "(VM TRACES AT LAST ANR 섹션 없음)"

    # ── 3. 각 블록별 스레드 파싱 (pid 정보 유지) ──────────────────────
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
        flat = [l for blk in blocks_by_pid.values() for l in blk]
        return "\n".join([header_line] + flat)

    # ── 4. BFS — ANR 프로세스 내에서만 락 체인 추적 ─────────────────
    # lock_holder는 (pid, lock_id) 키로 네임스페이스 → 프로세스 간 충돌 방지
    lock_holder = {}
    for t in all_threads:
        for lid in t['locked_ids']:
            lock_holder[(t['pid'], lid)] = t['tid']

    main_t = next((t for t in all_threads if t['name'] == 'main' and t['pid'] == pid), None)
    if main_t is None:
        main_t = next((t for t in all_threads if t['name'] == 'main'), None)
    if main_t is None:
        flat = [l for blk in blocks_by_pid.values() for l in blk]
        return "\n".join([header_line] + flat)

    anr_pid = main_t['pid']
    anr_tid_map = {t['tid']: t for t in all_threads if t['pid'] == anr_pid}

    relevant = set()  # (pid, tid) 튜플
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

    # ── 5. 락 경합 / GC 압박 / 컴포넌트 콜백 필터 — 모든 프로세스 적용 ──
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

    # ── 6. 출력 — 프로세스별 그룹화 ───────────────────────────────────
    _native_method = re.compile(r'^\s+at .+\(Native [Mm]ethod\)$')
    _native_frame  = re.compile(r'^\s*native:\s+#\d+\s+pc\s')

    out = [header_line, ""]
    # ANR 프로세스 먼저, 그 다음 관련 프로세스
    pids_ordered = [anr_pid] + [p for p in blocks_by_pid if p != anr_pid]
    for blk_pid in pids_ordered:
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
# [4] ANR 발생 시점 부근 logcat 키워드
# ──────────────────────────────────────────────────────────────────────────────
# MainThread/Lock/Binder 카테고리는 [2] ANR in 섹션과 [3] VM traces 가
# 훨씬 더 정확하게 다루므로 [4]에서는 제거. logcat 에서만 보이는
# GC/System/Render/IO 4 개 카테고리만 유지.
_GC_KW     = ["WaitForGcToComplete blocked",
              "Starting a blocking GC",
               "Throwing OutOfMemoryError",
               "Clamp target GC heap",
               "Forcing collection of SoftReferences",

                "GC_FOR_ALLOC",
                "GC concurrent",
                "Explicit concurrent mark sweep GC",
                "Background concurrent copying GC",
                "Suspending all threads",
                "OutOfMemoryError",
                "Failed to allocate",
                "Trim memory",]
_SYSTEM_KW = [
    "lowmemorykiller",
    "lmkd",
    "Kill '",
    "freeze ",
    "unfreeze ",
    "Freezer",
    "cpu starvation",
    "sched",
    "task stalled",
    "hung task",
]
_RENDER_KW = [
    "SurfaceFlinger",
    "BufferQueue",
    "dequeueBuffer",
    "queueBuffer",
    "EGL",
    "OpenGLRenderer",
    "HWUI",
    "FrameMissed",
    "jank",
    "RenderThread",
]
_IO_KW = [
    "I/O error",
    "Slow operation",
    "fsync",
    "storage",
    "SQLite",
    "database is locked",
    "disk full",
    "read blocked",
    "write blocked",
]

def extract_logcat_window(path: str, window_before: int = 120, window_after: int = 10) -> str:
    """ANR 시점 ±window 범위 logcat에서 GC/System/Render/IO 키워드 수집.
    (MainThread/Lock/Binder 는 [2][3] 섹션이 더 정확히 다루므로 제외)"""
    # 1단계: 마지막 ANR 타임스탬프 탐색
    anr_ts = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if " am_anr" in line:
                ts = _logcat_ts(line)
                if ts is not None:
                    anr_ts = ts  # break 없이 계속 갱신 → 마지막 값 유지

    t_start = (anr_ts - window_before) if anr_ts else None
    t_end   = (anr_ts + window_after)  if anr_ts else None

    found = {"GC": [], "System": [], "Render": [], "IO": []}
    kw_map = {
        "GC":         _GC_KW,
        "System":     _SYSTEM_KW,
        "Render":     _RENDER_KW,
        "IO":         _IO_KW,
    }
    MAX = 15
    in_window = (anr_ts is None)

    # 2단계: 키워드 수집
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if all(len(v) >= MAX for v in found.values()):
                break
            if anr_ts is not None:
                ts = _logcat_ts(line)
                if ts is not None:
                    in_window = (t_start <= ts <= t_end)
                    if ts > t_end + 60:
                        break
            if not in_window:
                continue
            for cat, kws in kw_map.items():
                if len(found[cat]) >= MAX:
                    continue
                for kw in kws:
                    if kw in line:
                        found[cat].append(line.rstrip())
                        break

    parts = []
    if anr_ts is not None:
        parts.append(f"(ANR 기준 -{window_before}s ~ +{window_after}s 범위 스캔)")
    else:
        parts.append("(am_anr 이벤트 미발견 — 파일 전체 스캔)")

    has_any = False
    for cat, lines in found.items():
        if lines:
            has_any = True
            parts.append(f"\n[{cat}]")
            parts.extend(lines)

    if not has_any:
        parts.append("(해당 키워드 없음)")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# [5] freeze 추정 시각 기준 사전 패키지 로그
# ──────────────────────────────────────────────────────────────────────────────
#
# 채택 기준: 라인 어딘가에 ANR 발생 패키지명이 등장하는 줄만.
# 시스템 전반 신호(lmkd/cpu starvation 등 패키지명 없는 메시지)는 [4]가 담당.
# 압축: 같은 태그 그룹(점 앞 prefix 일치)이 연속 3건 이상이면
#       앞 1건 + 압축 표시 + 마지막 1건 = 3줄 고정.
# ──────────────────────────────────────────────────────────────────────────────

# logcat 형식:
#   기본:        "MM-DD HH:MM:SS.mmm  PID  TID  LEVEL Tag : message"
#   dumpstate:   "MM-DD HH:MM:SS.mmm  UID  PID  TID  LEVEL Tag : message"
# UID 필드는 dumpstate 가 -uid 옵션으로 떴을 때 추가됨. 둘 다 지원.
# LEVEL 은 V/D/I/W/E/F 한 글자. Tag 는 공백/콜론 직전까지.
_LOGCAT_TAG_RE = re.compile(
    r"^\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\s+"
    r"(?:\d+\s+){2,3}"          # PID TID 또는 UID PID TID
    r"[VDIWEF]\s+"
    r"(\S+?)\s*:"
)


def _logcat_tag(line: str):
    """logcat 라인에서 태그 추출. 실패 시 None (압축 대상 제외용)."""
    m = _LOGCAT_TAG_RE.match(line)
    return m.group(1) if m else None


def _tag_group(tag: str) -> str:
    """태그를 압축 그룹 키로 변환.
    점이 있으면 첫 점 앞 prefix + ".*" 로 그룹화.
      - "HoneySpace.X", "HoneySpace.Y" → "HoneySpace.*"
      - "Choreographer[12345]" → "Choreographer[12345]" (점 없음, 그대로)
      - "Settings" → "Settings"
    같은 컴포넌트군에서 다양한 세부 클래스명을 찍는 패턴을 한 묶음으로 처리.
    """
    if "." in tag:
        return tag.split(".", 1)[0] + ".*"
    return tag


def _collapse_consecutive_same_tag(lines, keep_head: int = 1):
    """같은 태그 그룹이 연속되는 구간을 압축한다.

    그룹 기준: _tag_group() — 점 앞 prefix 가 같으면 같은 그룹.
    출력 형식: 앞 keep_head 건 + "  … [Group] × N건 압축" + 마지막 1건
    압축 발동 조건: 3건 이상 (keep_head=1 일 때 손익분기)
      - 2건 이하: 그대로 출력
      - 3건: 압축 (3줄 그대로 → 3줄 압축, 절약 0이지만 노이즈 표시 효과)
      - 4건 이상: 압축 (N줄 → 3줄로 고정, N-3건 절약)
    태그 추출 실패 라인은 압축하지 않고 그대로 두며, 연속 카운터를 리셋시킴.
    """
    if not lines:
        return lines
    out = []
    i, n = 0, len(lines)
    while i < n:
        tag_i = _logcat_tag(lines[i])
        if tag_i is None:
            # 태그 추출 실패 — 그대로 출력, 다음으로
            out.append(lines[i])
            i += 1
            continue
        group_i = _tag_group(tag_i)
        # 같은 그룹이 연속되는 구간 [i, j) 탐색
        j = i + 1
        while j < n:
            tag_j = _logcat_tag(lines[j])
            if tag_j is None or _tag_group(tag_j) != group_i:
                break
            j += 1
        run = lines[i:j]
        # keep_head + 압축표시 + 마지막1건 = 출력 (keep_head + 2) 줄
        # 압축 후 줄어들거나 같으려면 원본이 (keep_head + 2) 건 이상이어야 함
        if len(run) >= keep_head + 2:
            out.extend(run[:keep_head])
            collapsed = len(run) - keep_head - 1  # 마지막 1건은 별도 출력
            out.append(f"  … [{group_i}] × {collapsed}건 압축")
            out.append(run[-1])
        else:
            out.extend(run)
        i = j
    return out


def extract_pre_freeze_log(path: str, lookback: int = 30) -> str:
    """freeze 추정 시각 기준 lookback초 전부터 freeze 시점까지,
    ANR 발생 패키지명이 등장하는 라인만 시간순으로 추출."""
    pid, proc = _last_anr_info(path)
    if proc is None:
        return "(ANR 프로세스 정보 없음)"

    # 1단계: 마지막 ANR의 타임스탬프 + 지연시간 추출
    anr_ts = None
    anr_time_str = ""
    delay_ms = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
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

    delay_s  = delay_ms / 1000.0
    freeze_ts = anr_ts - delay_s
    t_start  = freeze_ts - lookback
    t_end    = freeze_ts  # freeze 이후 ~ ANR 시각 구간은 스캔하지 않음
                          # (멈춘 뒤 시스템이 찍은 진단 로그는 [1][2] 섹션이 담당)

    # 2단계: 윈도우 안에서 패키지명을 언급하는 라인만 수집
    out_lines = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            ts = _logcat_ts(line)
            if ts is None:
                continue
            if ts > t_end + 5:
                break
            if t_start <= ts <= t_end and proc in line:
                out_lines.append(line.rstrip())

    # 3단계: 같은 태그 연속 3건 이상이면 압축
    #   - 앞 1건 + "… [Tag] × N건 압축" + 마지막 1건 = 항상 3줄
    #   - 태그 추출 실패 라인은 압축 대상에서 제외 (그대로 출력)
    out_lines = _collapse_consecutive_same_tag(out_lines)

    header = (
        f"(ANR 시각: {anr_time_str}  /  지연: {delay_ms}ms  /  "
        f"freeze 추정: ANR-{delay_s:.1f}s  /  "
        f"스캔 범위: freeze-{lookback}s ~ freeze 시점  /  "
        f"매칭: 패키지명 '{proc}' 포함)"
    )
    if not out_lines:
        return f"{header}\n({proc} 관련 로그 없음)"
    return header + "\n" + "\n".join(out_lines)


# ──────────────────────────────────────────────────────────────────────────────
# [6] Crash 기록 — Java crash + native crash + TOMBSTONE 섹션
# ──────────────────────────────────────────────────────────────────────────────
#
# 파일 전체에서 모든 crash 를 수집한다 (ANR 윈도우로 자르지 않음).
# crash 는 ANR 직후 프로세스가 죽으면서 윈도우 밖에서 터지는 경우가 많기 때문.
# 대신 각 crash 의 타임스탬프와 ANR 시각의 상대 시간(Δ)을 함께 표기해
# 1차 분석 타임라인과 연결할 수 있게 한다.
#
# 수집 대상:
#   (a) Java crash  : "FATAL EXCEPTION" → 스택 트레이스 끝까지
#   (b) native crash: "Fatal signal" / "*** ***" → backtrace #NN pc 프레임
#   (c) TOMBSTONE   : dumpstate 의 "------ TOMBSTONE ------" 섹션 핵심부
# ──────────────────────────────────────────────────────────────────────────────

# Java crash 스택이 이어지는 라인 패턴 (트레이스 종료 판정용)
_JAVA_TRACE_CONT = re.compile(
    r"^\s*(at\s+\S|Caused by:|\.{3}\s+\d+\s+more|Suppressed:|"
    r"\$?[A-Za-z_][\w.$]*(Exception|Error|Throwable):)"
)


def _rel_to_anr(ts, anr_ts):
    """crash 타임스탬프와 ANR 시각의 상대 시간 문자열. ts/anr_ts 없으면 ''."""
    if ts is None or anr_ts is None:
        return ""
    d = ts - anr_ts
    sign = "+" if d >= 0 else "-"
    return f" (ANR Δ {sign}{abs(d):.1f}s)"


def _extract_java_crashes(path, anr_ts):
    """logcat 의 FATAL EXCEPTION 블록을 스택 트레이스째 추출.
    반환: [(ts, tstr, kind, block, lineno, proc), ...]"""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

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
        # 다음 줄들: Process:/PID, 예외 헤더, at..., Caused by... 를 따라감
        j = i + 1
        blank_run = 0
        while j < n:
            nxt = lines[j]
            # logcat prefix 제거 후 본문 판정 (태그 다음의 메시지부분)
            mb = re.search(r"\bE\s+\S+\s*:\s*(.*)$", nxt)
            content = mb.group(1) if mb else nxt.strip()
            # 프로세스명 추출 (Process: com.foo.bar, PID: 1234)
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
    """libc/DEBUG 의 Fatal signal + *** *** 경계 + backtrace 추출.
    반환: [(ts, tstr, kind, block, lineno, proc), ...]"""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

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
        # signal/abort/backtrace 라인을 모음. 비관련 라인 연속 8개면 종료.
        unrelated = 0
        while j < n and len(block) < 80:
            cur = lines[j]
            # dumpstate 섹션 헤더(------ ... ------)를 만나면 native 블록 종료
            # (TOMBSTONE 등은 별도 추출기가 처리하므로 여기서 흡수하면 중복됨)
            if cur.lstrip().startswith("------"):
                break
            if re.search(
                r"Fatal signal|signal \d+ \(SIG|Abort message|backtrace:|"
                r"#\d{2} pc |\*\*\* \*\*\*|pid: \d+, tid: \d+|"
                r"name: .*>>> .* <<<|libc :|DEBUG\s*:", cur
            ):
                block.append(cur.rstrip())
                unrelated = 0
                # 프로세스명 추출: ">>> com.foo <<<" 또는 "name: com.foo"
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
    """dumpstate 의 ------ TOMBSTONE ------ 섹션에서 핵심부만 추출.
    반환: [(ts, tstr, kind, block, lineno, proc), ...]"""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    i, n = 0, len(lines)
    while i < n:
        if "TOMBSTONE" not in lines[i] or not lines[i].lstrip().startswith("---"):
            i += 1
            continue
        lineno = i + 1
        j = i + 1
        block = []
        proc = "?"
        # 다음 ------ 섹션 헤더 전까지. abort/signal/backtrace 핵심만 추림.
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
                # 프로세스명: Cmdline > >>> name <<< > name: 우선순위
                if proc == "?":
                    mp = (re.search(r"Cmdline:\s*(\S+)", cur)
                          or re.search(r">>>\s*([\w./:]+)\s*<<<", cur)
                          or re.search(r"\bname:\s*(\S+)", cur))
                    if mp:
                        proc = mp.group(1)
                if kept >= 60:  # backtrace 가 매우 길 수 있어 상한
                    block.append("      … (backtrace 이하 생략)")
                    break
            j += 1
        if block:
            out.append((None, "(tombstone 섹션)", "TOMBSTONE", block, lineno, proc))
        i = max(j, i + 1)
    return out


def extract_crash_records(path: str) -> str:
    """파일 전체에서 Java/native crash + TOMBSTONE 을 모두 수집.
    출력: ANR 패키지 관련 + 최근 1건을 상세, 나머지는 인덱스 한 줄씩."""
    # ANR 시각(상대 시간 표기용) + ANR 패키지명(대표 선정용)
    anr_ts = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
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

    # 정렬: 타임스탬프 있는 것 시간순, tombstone(None) 은 뒤로
    crashes.sort(key=lambda c: (c[0] is None, c[0] if c[0] is not None else 0))

    # 대표 1건 선정:
    #   ANR 패키지 관련 crash 중 → 시각 있고 ANR 시각에 가장 가까운 것 우선
    #   (시각 없는 tombstone 은 보통 같은 native crash 의 부산물이라 후순위)
    #   ANR 패키지 관련이 없으면 → 전체 중 ANR 시각에 가장 가까운 것
    def selection_key(c):
        ts = c[0]
        if ts is None or anr_ts is None:
            # 시각 없음 → 가장 후순위
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

    # 출력 조립
    parts = [
        f"(총 {len(crashes)}건 발견 — 파일 전체 스캔)",
        f"대표 선정 기준: {sel_reason}",
        "",
        "─── 대표 Crash (상세) ───",
    ]
    rep_ts, rep_tstr, rep_kind, rep_block, rep_lineno, rep_proc = representative
    rel = _rel_to_anr(rep_ts, anr_ts)
    parts.append(
        f"[{rep_kind}]  {rep_tstr}{rel}  proc={rep_proc}  @ line {rep_lineno}"
    )
    parts.extend(rep_block)

    # 나머지 인덱스 (대표 제외)
    others = [c for c in crashes if c is not representative]
    if others:
        parts.append("")
        parts.append(f"─── 기타 Crash 인덱스 ({len(others)}건, 상세는 원본 파일 참조) ───")
        for c in others:
            ts, tstr, kind, _, lineno, proc = c
            rel = _rel_to_anr(ts, anr_ts)
            parts.append(
                f"  [{kind:<9s}] {tstr}{rel}  proc={proc}  @ line {lineno}"
            )

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# 파싱 실행 및 저장
# ──────────────────────────────────────────────────────────────────────────────

SECTIONS = [
    ("[1] am_anr 이벤트",                          extract_am_anr),
    ("[2] ANR in  (ActivityManager 섹션)",          extract_anr_in),
    ("[3] VM TRACES AT LAST ANR  (스레드 덤프)",   extract_vm_traces),
    ("[4] ANR 부근 logcat 키워드  (-120s ~ +10s)",  extract_logcat_window),
    ("[5] freeze 이전 패키지 로그  (freeze-30s ~ freeze)", extract_pre_freeze_log),
    ("[6] Crash 기록  (Java / native / TOMBSTONE, 파일 전체)", extract_crash_records),
]

SEP = "=" * 80


def parse_and_save(dumpstate_path: str) -> str | None:
    dumpstate_path = dumpstate_path.strip().strip('"').strip("'")
    if not os.path.isfile(dumpstate_path):
        print(f"  ⚠ 파일을 찾을 수 없습니다: {dumpstate_path}")
        return None

    print(f"\n파싱 중: {os.path.basename(dumpstate_path)}")

    output_lines = [
        "ANR 파싱 결과",
        f"원본 : {os.path.basename(dumpstate_path)}",
        f"일시 : {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}",
        SEP,
    ]

    for title, fn in SECTIONS:
        output_lines += [f"\n{SEP}", title, SEP]
        try:
            output_lines.append(fn(dumpstate_path))
        except Exception as e:
            output_lines.append(f"(오류: {e})")
        print(f"  ✓ {title}")

    result = "\n".join(output_lines)

    base = os.path.splitext(dumpstate_path)[0]
    out_path = base + "_anr_parsed.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"\n  → 저장 완료: {out_path}")
    return out_path


def main():
    if len(sys.argv) > 1:
        parse_and_save(" ".join(sys.argv[1:]))
        return

    print("=" * 50)
    print("ANR dumpstate 파서")
    print("dumpstate 파일을 드래그하거나 경로를 입력하세요.")
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
        parse_and_save(raw)


if __name__ == "__main__":
    main()
