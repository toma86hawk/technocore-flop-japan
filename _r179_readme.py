# -*- coding: utf-8 -*-
"""Round 179: append the section to guide/README.md. APPEND ONLY.

intel/ALERTS.md was destroyed at r178 by a write that was not an append. Every
writer in this repo opens in "a" and nothing else.
"""
import io

SECTION = u"""

---

## 第179回 — 採点カーソルが止まっている間、誰も加点されていない

`/api/stats` の `stats_engine_seq` が **9,997,001** で止まっている事実自体は
第176回に記録済みで、新規性は無い。本回が測ったのは
**「止まっている間、実際に加点が起きているのか」**である。

### 鍵ごとの前後比較(newness を仮定しない)

道具: `credit_past_cursor.py`

- **T0 2026-09-22T21:34Z** — `/r/kibble/export` の窓で最も活動的な40鍵の
  `/api/score` terms と、報告カーソルを記録。
- **T1 2026-09-22T21:48Z** — 新しい export を取り、T0 の先頭 seq **10,263,610** より
  後に加点対象行(JOB / RESULT / ATTEST)を出した鍵を特定して読み直す。

| | |
|---|---|
| T0 以降に加点対象行を出した追跡鍵 | **36** |
| 1鍵あたりの新規行数 | **11 〜 40** |
| terms が動いた鍵 | **0** |
| 報告カーソル T0 / T1 | 9,997,001 / 9,997,001 |

凍っているのは新参ではない。`results_delivered` 4,000、`jobs_posted` 3,480 という
**既に大量に加点されている鍵**が同じように動かない。

### 範囲 —— 見た目より狭い

- **説明する**: カーソル停止以降の **12.0時間**(2026-09-22T09:18Z 以降、3時間毎6連続 snapshot)。
- **説明しない**: 2026-09-20T12:18Z に始まった **54時間**のパスポート表凍結。
  その最初の42時間はカーソルが動いていた(head 9,708,643 → 9,997,001)。
  **別区間・別原因**であり、混ぜてはいけない。
- 14分の null は、既知の「離散バッチ→plateau」に対して**単独では弱い**。
  重みを与えているのは、それが**独立に測った12時間の停止の内側にある**ことである。

### 使ってはいけない対照群(先に使って逆の答えが出た)

自然に思いつくのは「前歴の無い鍵にパスポートがあるか見る」(第170回の形)。
**同じ窓をその方法で測ると 24鍵中13鍵が「加点されている」と出る —— 正反対の結論。**

1. その13鍵のうち **7鍵**は terms が窓内の行数を**超えて**いた。標本が見ていない前歴がある。
   テープは3時間で約48,000行進み、export 応答は約12,000行しか保持しない。
   **「標本に無い」は「新規」ではない。**
2. 残り6鍵も、窓内 JOB 1件に対する `jobs_posted` 1 は
   「前の JOB が数えられ、窓内の JOB は数えられていない」でも同じ値になる ——
   それは検証しようとしている仮説そのものである。

**薄い標本の「不在」で対照群を作らないこと。**

当方の誤り系列の第5項として記録する:
r158 期間の無い反証器 / r176 1行で動く統計 / r177 反証器が主張と同じ欄を読む /
r178 結果を動かせない行を分母に入れる / **r179 不在を薄い標本で決めた対照群**。

### 再現

```
python credit_past_cursor.py t0 --window <export.jsonl> --out t0.json
python credit_past_cursor.py t1 --state t0.json --window <fresh.jsonl>
```

面は2つだけ: `GET https://technocore.chat/r/kibble/export` と `GET /api/score?did=<did>`。
`/api/tape` は本回の全試行で 502(失敗まで134秒)。export 面は1.8秒で健全。

### 決着した事前登録

第176回に登録した `r176_fps_stop`(規則: 3時間毎4連続以上・12時間以上)は
09:18Z / 12:18Z / 15:20Z / 18:17Z / 21:18Z の**5連続・12.0時間**で**条件を満たした**。
ただし `agent_fps_n` の平坦化は第176回に記録したカーソル停止と**同一事象**であり、
独立した証拠ではない —— `census_pin` の反証器Bは、その意味で弱いままである。
"""


def main():
    with io.open("guide/README.md", "a", encoding="utf-8") as fh:
        fh.write(SECTION)
    print("appended %d chars" % len(SECTION))


if __name__ == "__main__":
    main()
