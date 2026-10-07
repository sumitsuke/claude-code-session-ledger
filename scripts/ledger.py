"""Read Claude Code transcripts (jsonl) and count each assistant response once.

One response is often written as several jsonl lines that share the same message.id.
Counting lines double-counts; counting only the first line drops most of the output.
Here every response is reduced to one record: the maximum of each usage field over its lines.
"""

import glob
import json
import os
from datetime import datetime

NL = b"\n"
ESCAPED_NL = b"\\n"


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def transcripts(projects_dir, subagents=False, since=None):
    """Yield jsonl paths under ~/.claude/projects (main sessions, or subagents when subagents=True)."""
    pat = (
        os.path.join(projects_dir, "*", "*", "subagents", "*.jsonl")
        if subagents
        else os.path.join(projects_dir, "*", "*.jsonl")
    )
    for p in sorted(glob.glob(pat)):
        if since is None or os.path.getmtime(p) >= since:
            yield p


def records(path, max_join=20):
    """Yield (record, n_physical_lines) from a jsonl file.

    A record that was written with a raw newline inside a string spans several physical lines (seen once
    in 170 real transcripts); those lines are re-joined with an escaped newline and parsed again.
    What still does not parse is yielded as (None, 1).
    """
    with open(path, "rb") as f:
        lines = f.read().split(NL)
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        buf, k = lines[i], 1
        while True:
            try:
                rec = json.loads(buf.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                if k >= max_join or i + k >= len(lines):
                    yield None, 1
                    i += 1
                    break
                buf, k = buf + ESCAPED_NL + lines[i + k], k + 1
                continue
            yield rec, k
            i += k
            break


def responses(path, model_substr=None):
    """Return (responses, bad, joined): one dict per assistant response, sorted by time.

    ctx = input + cache_read + cache_creation (the context the response was sent with).
    bad = lines that could not be parsed even after re-joining (callers stop when it is not 0).
    joined = records that had been split over several physical lines and were re-joined.
    """
    best, bad, joined = {}, 0, 0
    for o, n in records(path):
        if o is None:
            bad += 1
            continue
        if n > 1:
            joined += 1
        if o.get("type") != "assistant" or not o.get("timestamp"):
            continue
        m = o.get("message") or {}
        u = m.get("usage") or {}
        if not u:
            continue
        if model_substr and model_substr not in str(m.get("model")):
            continue
        k = m.get("id") or o.get("uuid")
        r = best.setdefault(k, {"t": ts(o["timestamp"]), "model": m.get("model"), "inp": 0, "cr": 0, "cc": 0, "out": 0})
        r["t"] = min(r["t"], ts(o["timestamp"]))
        for a, b in (
            ("inp", "input_tokens"),
            ("cr", "cache_read_input_tokens"),
            ("cc", "cache_creation_input_tokens"),
            ("out", "output_tokens"),
        ):
            r[a] = max(r[a], u.get(b) or 0)
    rs = sorted(best.values(), key=lambda r: r["t"])
    for r in rs:
        r["ctx"] = r["inp"] + r["cr"] + r["cc"]
    return rs, bad, joined
