#!/usr/bin/env python3
"""
anr_parse.py
dumpstate 파일에서 ANR 관련 섹션을 추출해 텍스트 파일로 저장.

사용법:
  python anr_parse.py <dumpstate_path>
  또는 실행 후 경로 드래그/입력

출력 섹션:
  [1] am_anr       — logcat am_anr 이벤트
  [2] ANR in       — ActivityManager ANR 헤더 + CPU 사용량 + PSI 메모리
  [3] VM traces    — VM TRACES AT LAST ANR 스레드 덤프
  [4] 부근 logcat  — ANR 발생 시점 -120s ~ +10s 키워드 (GC / System / Render / IO)
  [5] freeze 이전  — freeze 추정 시각 기준 패키지 로그
  [6] Crash 기록   — Java / native crash / TOMBSTONE

외부 라이브러리 불필요 (표준 라이브러리만 사용).
Python 3.8 이상 호환.
"""

import os
import re
import sys
from datetime import datetime as _dt
from typing import Optional

__version__ = "1.2"


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

    last_anr_lineno = -1
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            c = _am_content(line)
            if c and "ANR in " in c:
                last_anr_lineno = i

    if last_anr_lineno == -1:
        return "(ActivityManager ANR 섹션 없음)"

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

    header_line = ""
    blocks_by_pid = {}
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
                    current_pid = None
                    continue
                blocks_by_pid.setdefault(current_pid, []).append(s)

    # CPU 과부하로 tombstoned 응답 없을 때 발생하는 덤프 실패 감지.
    # 실패한 PID 블록에는 libdebuggerd_client 오류 뒤 Waiting Channels /
    # 불완전한 native 프레임이 섞여 있으므로 블록을 모두 제거한다.
    failed_dump_pids = set()
    for blk_pid, blk_lines in list(blocks_by_pid.items()):
        for l in blk_lines:
            if "libdebuggerd_client: failed" in l:
                failed_dump_pids.add(blk_pid)
                blocks_by_pid[blk_pid] = []
                break

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
    r"(?:\d+\s+){2,3}"
    r"[VDIWEF]\s+"
    r"(\S+?)\s*:"
)


def _logcat_tag(line: str):
    m = _LOGCAT_TAG_RE.match(line)
    return m.group(1) if m else None


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
    "Freezer", "cpu starvation", "sched", "task stalled", "hung task",
]
_RENDER_KW = [
    "SurfaceFlinger", "BufferQueue", "dequeueBuffer", "queueBuffer",
    "EGL", "OpenGLRenderer", "HWUI", "FrameMissed", "jank", "RenderThread",
]
_IO_KW = [
    "I/O error", "Slow operation", "fsync", "storage", "SQLite",
    "database is locked", "disk full", "read blocked", "write blocked",
]


def extract_logcat_window(path: str, window_before: int = 120, window_after: int = 10) -> str:
    """ANR 시점 ±window 범위 logcat에서 GC/System/Render/IO 키워드 수집.
    각 카테고리 내 연속 동일 태그는 압축."""
    anr_ts = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if " am_anr" in line:
                ts = _logcat_ts(line)
                if ts is not None:
                    anr_ts = ts

    t_start = (anr_ts - window_before) if anr_ts else None
    t_end   = (anr_ts + window_after)  if anr_ts else None

    found = {"GC": [], "System": [], "Render": [], "IO": []}
    kw_map = {"GC": _GC_KW, "System": _SYSTEM_KW, "Render": _RENDER_KW, "IO": _IO_KW}
    MAX = 15
    in_window = (anr_ts is None)

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
            parts.extend(_collapse_consecutive_same_tag(lines))

    if not has_any:
        parts.append("(해당 키워드 없음)")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# [5] freeze 추정 시각 기준 사전 패키지 로그
# ──────────────────────────────────────────────────────────────────────────────

def extract_pre_freeze_log(path: str, lookback: int = 30) -> str:
    """freeze 추정 시각 기준 lookback초 전부터 freeze 시점까지 패키지 로그 추출."""
    pid, proc = _last_anr_info(path)
    if proc is None:
        return "(ANR 프로세스 정보 없음)"

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

    delay_s   = delay_ms / 1000.0
    freeze_ts = anr_ts - delay_s
    t_start   = freeze_ts - lookback
    t_end     = freeze_ts

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

SECTIONS = [
    ("[1] am_anr 이벤트",                          extract_am_anr),
    ("[2] ANR in  (ActivityManager 섹션)",          extract_anr_in),
    ("[3] VM TRACES AT LAST ANR  (스레드 덤프)",   extract_vm_traces),
    ("[4] ANR 부근 logcat 키워드  (-120s ~ +10s)",  extract_logcat_window),
    ("[5] freeze 이전 패키지 로그  (freeze-30s ~ freeze)", extract_pre_freeze_log),
    ("[6] Crash 기록  (Java / native / TOMBSTONE, 파일 전체)", extract_crash_records),
]

SEP = "=" * 80


def parse_and_save(dumpstate_path: str) -> Optional[str]:
    dumpstate_path = dumpstate_path.strip().strip('"').strip("'")
    if not os.path.isfile(dumpstate_path):
        print(f"  ⚠ 파일을 찾을 수 없습니다: {dumpstate_path}")
        return None

    print(f"\n파싱 중: {os.path.basename(dumpstate_path)}")

    output_lines = [
        "ANR 파싱 결과",
        f"파서 버전 : {__version__}",
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
    print(f"ANR dumpstate 파서  v{__version__}")
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
