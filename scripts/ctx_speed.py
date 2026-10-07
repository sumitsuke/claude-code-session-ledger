"""Does a bigger context make Claude Code slower? Bucket responses by context size.

For each assistant response (one per message.id): context = input + cache_read + cache_creation,
wait = first line of the response - the preceding user/tool-result line,
speed = output tokens / (last line - preceding user line), for responses with >= 300 output tokens.

    python scripts/ctx_speed.py --projects ~/.claude/projects --model 5-5
"""

import argparse
import glob
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402

BUCKETS = [(0, 50e3), (50e3, 100e3), (100e3, 200e3), (200e3, 400e3), (400e3, 2e6)]


def rows_of(path, model_substr, kind):
    out, prev, cur, msgs, bad = [], None, None, [], 0
    for o, _n in ledger.records(path):
        if o is None:
            bad += 1
            continue
        if not o.get("timestamp") or o.get("type") not in ("user", "assistant"):
            continue
        t = ledger.ts(o["timestamp"])
        m = o.get("message") or {}
        if o["type"] == "user":
            prev, cur = t, None
            continue
        if model_substr not in (m.get("model") or ""):
            continue
        if cur is None or cur["id"] != m.get("id"):
            cur = {"id": m.get("id"), "model": m.get("model"), "first": t, "last": t, "prev": prev, "u": {}}
            msgs.append(cur)
        cur["last"] = t
        for k, v in (m.get("usage") or {}).items():
            if isinstance(v, int):
                cur["u"][k] = max(cur["u"].get(k, 0), v)
    for c in msgs:
        u = c["u"]
        if c["prev"] is None or not u:
            continue
        ctx = u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("input_tokens", 0)
        gen = c["last"] - c["prev"]
        if 0 < gen < 900:
            out.append(
                (c["model"].replace("claude-", ""), kind, ctx, c["first"] - c["prev"], gen, u.get("output_tokens", 0))
            )
    return out, bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", required=True, help="~/.claude/projects (all projects) or one project dir")
    ap.add_argument("--model", default="5-5", help="substring of message.model")
    a = ap.parse_args(argv)
    root = os.path.expanduser(a.projects)
    rows, bad = [], 0
    for kind, pat in (("main", os.path.join(root, "**", "*.jsonl")),):
        for f in glob.glob(pat, recursive=True):
            r, b = rows_of(f, a.model, "subagent" if os.sep + "subagents" + os.sep in f else kind)
            rows += r
            bad += b
    if bad:
        print(f"FAIL: {bad} unparsable lines", file=sys.stderr)
        return 1
    print(
        "model | where | context | responses | wait to first line (median) | speed of responses with >=300 output tok/s (n)"
    )
    for model in sorted({r[0] for r in rows}):
        for lo, hi in BUCKETS:
            sel = [r for r in rows if r[0] == model and lo <= r[2] < hi]
            if len(sel) < 5:
                continue
            sp = [r[5] / r[4] for r in sel if r[5] >= 300 and r[4] > 0]
            kinds = "/".join(sorted({r[1] for r in sel}))
            speed = f"{st.median(sp):.0f} ({len(sp)})" if len(sp) >= 3 else "-"
            print(
                f"{model} | {kinds} | {int(lo / 1e3)}k-{int(hi / 1e3)}k | {len(sel)} | {st.median(r[3] for r in sel):.1f}s | {speed}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
