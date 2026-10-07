"""Synthetic inputs only (no real transcripts). Run: python -m unittest discover -s tests"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import compact_sim  # noqa: E402
import handoff_sim  # noqa: E402
import ledger  # noqa: E402


def line(mid, t, inp=1, cr=0, cc=0, out=0, model="claude-opus-5-5", typ="assistant"):
    u = {"input_tokens": inp, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc, "output_tokens": out}
    return json.dumps({"type": typ, "timestamp": t, "message": {"id": mid, "model": model, "usage": u}})


class LedgerTest(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("wb", suffix=".jsonl", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_one_response_per_message_id_max_of_lines(self):
        body = "\n".join(
            [
                line("m1", "2026-10-01T00:00:00Z", cr=1000, out=10),
                line("m1", "2026-10-01T00:00:01Z", cr=1000, out=50),
                line("m2", "2026-10-01T00:00:05Z", cr=1200, cc=30, out=7),
            ]
        ).encode()
        rs, bad, joined = ledger.responses(self.write(body))
        self.assertEqual((len(rs), bad, joined), (2, 0, 0))
        self.assertEqual(rs[0]["out"], 50)  # max over the two lines, not the first and not the sum
        self.assertEqual(rs[0]["ctx"], 1001)
        self.assertEqual(rs[1]["ctx"], 1231)

    def test_split_record_is_rejoined_and_garbage_is_counted(self):
        good = line("m1", "2026-10-01T00:00:00Z", cr=5)
        split = b'{"type": "user", "timestamp": "2026-10-01T00:00:02Z", "message": {"content": "a\nb"}}'
        body = good.encode() + b"\n" + split + b"\n" + b"{not json\n"
        rs, bad, joined = ledger.responses(self.write(body))
        self.assertEqual((len(rs), bad, joined), (1, 1, 1))


class SimTest(unittest.TestCase):
    def test_compact_sim_by_hand(self):
        # c: 0 -> 100 -> 250 -> 400 reaches W=300: read 400 once more for the summary, continue at S+R=60.
        # total = 100 + 250 + 400 + 60 = 810, one compaction.
        self.assertEqual(compact_sim.sim([[0, 100, 250, 400]], w=300, r=10, s=50), (810, 1))

    def test_compact_sim_does_not_replay_real_drop(self):
        # a real compaction (drop > 300K) is not replayed: the context stays where the replay put it.
        self.assertEqual(compact_sim.sim([[0, 500_000, 100_000]], w=10**9, r=0, s=0), (1_000_000, 0))

    def test_handoff_by_hand(self):
        # 100 -> 400 passes T=300: one hand-off, continue at new_start=50, cost 3*300 + relearn 1000.
        # read = 100 + 50 + (900 + 1000) = 2050
        self.assertEqual(handoff_sim.replay([[100, 400]], t_line=300, new_start=50, relearn=1000), (2050, 1))


if __name__ == "__main__":
    unittest.main()
