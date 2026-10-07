"""Where should you hand off to a new session? Replay your own transcripts with a hand-off line T.

A different operation from auto-compact: here the context is thrown away and a new session starts
from a hand-off note. For each line T: when a session's (replayed) context passes T, count one hand-off,
add the cost of writing the note (3 reads of T) and of the new session re-reading it (--relearn),
and continue from --new-start. Reports total read vs. what was actually read.

    python scripts/handoff_sim.py --projects ~/.claude/projects/<project-dir> --since 2026-09-26 --days 7
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402


def replay(sessions, t_line, new_start, relearn):
    tot = mig = over = 0
    for s in sessions:
        off = 0
        for c in s:
            sim = c - off
            if sim > t_line:
                mig += 1
                over += relearn + 3 * t_line  # writing the note (3 calls) + re-reading in the new session
                off = c - new_start
                sim = new_start
            if sim < new_start * 0.5:  # the real session shrank (e.g. auto-compact): follow it
                off = 0
                sim = c
            tot += sim
    return tot + over, mig


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", required=True)
    ap.add_argument("--since", required=True, help="YYYY-MM-DD (UTC); responses before it are ignored")
    ap.add_argument("--days", type=float, default=7.0, help="length of the period, for the per-day rate")
    ap.add_argument(
        "--new-start", type=int, default=94_000, help="context of a fresh session's first response (measure yours)"
    )
    ap.add_argument(
        "--relearn", type=int, default=1_350_000, help="tokens a new session reads to pick up the note (measure yours)"
    )
    ap.add_argument("--lines", default="300000,400000,500000,600000,700000")
    a = ap.parse_args(argv)
    since = datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    projects = os.path.expanduser(a.projects)
    sessions, bad, joined = [], 0, 0
    for f in sorted(os.listdir(projects)):
        p = os.path.join(projects, f)
        if not f.endswith(".jsonl") or os.path.getmtime(p) < since:
            continue
        rs, b, j = ledger.responses(p)
        bad, joined = bad + b, joined + j
        seq = [r["ctx"] for r in rs if r["t"] >= since]
        if seq:
            sessions.append(seq)
    if bad:
        print(f"FAIL: {bad} unparsable lines", file=sys.stderr)
        return 1
    actual = sum(sum(s) for s in sessions)
    print(
        f"sessions {len(sessions)} / responses {sum(len(s) for s in sessions)} / actual read {actual / 1e8:.2f} x1e8 / re-joined {joined}"
    )
    for t in (int(x) for x in a.lines.split(",")):
        tot, mig = replay(sessions, t, a.new_start, a.relearn)
        print(
            f"  T={t:>9,}: read {tot / 1e8:6.2f} x1e8 ({100 * (tot - actual) / actual:+.0f}% vs actual) / hand-offs {mig} ({mig / a.days:.1f}/day)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
