# claude-code-session-ledger

**Claude Code の会話の記録（`~/.claude/projects/**/*.jsonl`）を、応答ごとに 1 回だけ数えて、自分の使い方に合う線を出す道具。**
Count each response in your Claude Code transcripts once, then replay them with a different auto-compact line or hand-off line. Standard library only.

記事: [Claude Code の自動の要約の線を引き直す計算——32 本の会話・16,449 応答に当てはめた記録](https://sumitsuke.jp/lab/auto-compact-line-recompute/)（Sumitsuke Lab・2026-10-07）

## 何をするか

| スクリプト | 問い | 出すもの |
|---|---|---|
| `scripts/compact_sim.py` | 自動の要約（auto-compact）を何万トークンで掛けると、読み込みの合計と要約の回数はどう変わるか | 線ごとの読み合計（既定の約 96.7 万との比）と回数。要約の後の上乗せ R は、実際の要約の前後の増えの**中央どうしの差** |
| `scripts/handoff_sim.py` | 文脈を捨てて新しい会話へ移る線 T を置くと、読み込みと移行の回数はどう変わるか | 線ごとの読み合計（実際との比）と移行の回数 |
| `scripts/ctx_speed.py` | 文脈が大きいと遅くなるか | 文脈の区分ごとの、最初の行までの待ちと出力の速さ（中央値） |
| `scripts/ledger.py` | （共通）1 つの応答が記録の複数行に分かれる | `message.id` ごとに usage の各項目の最大で 1 回だけ数える |

**計算であって、線を変えて実際に回した結果ではありません。** 記録された「応答ごとの文脈の増え」を、別の線で積み直しています。

## 走らせ方

Python 3.8 以上・外部のパッケージなし。

```bash
# 自動の要約の線（1 つのプロジェクトの会話の記録のフォルダを渡す）
python scripts/compact_sim.py --projects ~/.claude/projects/<project-dir> --since 2026-09-29

# 新しい会話へ移る線（--new-start と --relearn は自分の記録で測った値に置き換える）
python scripts/handoff_sim.py --projects ~/.claude/projects/<project-dir> --since 2026-09-26 --days 7

# 文脈の大きさと速さ（全プロジェクト・作業員の記録も含む）
python scripts/ctx_speed.py --projects ~/.claude/projects --model 5-5
```

- 記録の中の会話の本文は読み込みますが、出力には数だけを出します。
- 読めない行があると止まります（終了コード 1）。文字列の中に生の改行が入って複数行に割れた記録は、つなぎ直して読み、つないだ件数を印字します（当方の 170 本の記録で 1 件）。
- `--since` はファイルの更新時刻で選びます。古い会話でも、後から更新されると対象に入ります（当方の記録では、同じ条件で 10-06 は 32 本・10-07 は 170 本）。比べるときは、記録の写しを取ってから走らせてください。

## 試験

```bash
python -m unittest discover -s tests
```

合成の入力だけを使います（本物の記録は使いません）。`message.id` ごとの最大・割れた行のつなぎ直し・読めない行の数え上げ・要約と移行の積み直しを、手で計算した値と比べます。数え方を壊した写し（最大を足し算に変える・実際の要約の縮みを積み直す）で、2 本が赤になることを確かめています。

## データ（`data/`）

記事の数は、ここに置いた**凍結した出力**が正です。上のスクリプトは同じ方法を引数つきで書き直したもので、今日の記録で走らせると数は変わります。

| ファイル | 中身 |
|---|---|
| `compact_sim_output.txt` | 2026-10-06 の自動の要約の線の計算（会話 32 本・応答 16,449 回・R=0／23,725／47,450） |
| `actual_compactions.txt` | 記録に残った要約の位置（自動・手動）。会話の ID は番号に置き換えた |
| `replay_threshold_output.txt` | 2026-10-03 の新しい会話へ移る線の計算（会話 58 本・応答 5,589 回） |
| `ctx_speed_output.txt` | 2026-10-03 の文脈の区分と速さ |

## 第三者が検証できる範囲

- 確かめられる: 数え方（スクリプトと試験）・凍結した出力の数どうしの計算（例: 線 60 万の読み合計 ÷ 既定の線の読み合計）。
- 確かめられない: 当方の会話の記録そのもの（作業の中身が入るため公開していません）。数は 1 人・1 環境・1 週間の記録からの値で、一般の値ではありません。

## ライセンス

コードは MIT（`LICENSE`）、データと出力は CC BY 4.0（`DATA_LICENSE`）。
