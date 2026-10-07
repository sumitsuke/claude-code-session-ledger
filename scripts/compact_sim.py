"""Where should auto-compact fire? Replay your own transcripts with a different line.

1. For every main session (subagents excluded), take the context of each response, in time order.
2. Find the real compactions (the context drops by more than 300K at once). Measure how much faster the
   context grows in the 20 responses after them than usual: R = median(post) - 20 * median(usual step).
   S = median context right after a compaction.
3. For each line W, re-accumulate the same steps. When the context reaches W: add one read of that
   context (the summary call), continue from S + R. Report total read (sum of contexts) and the count.

This is a calculation on recorded steps, not a measurement with a different setting.

    python scripts/compact_sim.py --projects ~/.claude/projects/<project-dir> --since 2026-09-29
"""

import argparse
import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402

DROP = 300_000


def load(projects, since, model, min_calls):
    traces, bad, joined = [], 0, 0
    for p in sorted(os.path.join(projects, f) for f in os.listdir(projects) if f.endswith(".jsonl")):
        if since and os.path.getmtime(p) < since:
            continue
        rs, b, j = ledger.responses(p, model)
        bad, joined = bad + b, joined + j
        seq = [r["ctx"] for r in rs]
        if len(seq) >= min_calls:
            traces.append(seq)
    return traces, bad, joined


def overhead(traces):
    post, usual, s_obs, at = [], [], [], []
    for seq in traces:
        for i in range(1, len(seq)):
            if seq[i - 1] - seq[i] > DROP:
                s_obs.append(seq[i])
                at.append(seq[i - 1])
                post.append(sum(max(0, seq[j] - seq[j - 1]) for j in range(i + 1, min(i + 21, len(seq)))))
        usual += [max(0, seq[j] - seq[j - 1]) for j in range(1, len(seq)) if seq[j - 1] - seq[j] <= DROP]
    if not post:
        return None
    r = max(0, statistics.median(post) - 20 * statistics.median(usual))
    return {"n": len(post), "at": statistics.median(at), "S": statistics.median(s_obs), "R": r}


def sim(traces, w, r, s):
    tot = comp = 0
    for seq in traces:
        c = seq[0]
        for j in range(1, len(seq)):
            d = seq[j] - seq[j - 1]
            if d < -DROP:
                d = 0  # do not replay the real compaction's drop
            c = max(c + d, s if comp else 0)
            if c >= w:
                tot += c  # the summary call reads the context once
                comp += 1
                c = s + r
            tot += c
    return tot, comp


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", required=True, help="one project dir under ~/.claude/projects")
    ap.add_argument("--since", help="YYYY-MM-DD (by file mtime, UTC)")
    ap.add_argument("--model", default="opus", help="substring of message.model to keep (default: opus)")
    ap.add_argument("--min-calls", type=int, default=30)
    ap.add_argument(
        "--default-line", type=int, default=967_000, help="the line to compare against (default 967K for a 1M window)"
    )
    ap.add_argument("--lines", default="200000,300000,400000,500000,600000,700000,800000")
    a = ap.parse_args(argv)
    since = datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() if a.since else None
    traces, bad, joined = load(os.path.expanduser(a.projects), since, a.model, a.min_calls)
    if bad:
        print(f"FAIL: {bad} unparsable lines", file=sys.stderr)
        return 1
    if not traces:
        print("FAIL: no sessions", file=sys.stderr)
        return 1
    print(
        f"sessions {len(traces)} / responses {sum(len(s) for s in traces)} / records re-joined from split lines {joined}"
    )
    o = overhead(traces)
    if o is None:
        print("FAIL: no real compaction in these sessions (R and S cannot be set)", file=sys.stderr)
        return 1
    print(
        f"real compactions {o['n']} / context at compaction (median) {o['at']:,.0f} / S {o['S']:,.0f} / R {o['R']:,.0f}"
    )
    lines = [int(x) for x in a.lines.split(",")] + [a.default_line]
    for rx in (0, o["R"], 2 * o["R"]):
        rows = [(w, *sim(traces, w, rx, o["S"])) for w in lines]
        base = rows[-1][1]
        print(f"--- R={rx:,.0f}")
        for w, t, n in rows:
            print(
                f"  line {w:>9,}: read {t / 1e8:7.2f} x1e8 ({100 * (t / base - 1):+6.1f}% vs {a.default_line:,}) / compactions {n}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
