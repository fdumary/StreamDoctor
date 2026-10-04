# StreamTrust synthetic scenarios

`streamtrust.json` contains 22 authored synthetic cases covering missing evidence, mock
AI, conflicting observations, plausible unusual pH, duplicated images, peer agreement,
and prior review history. The dataset and its authored labels are offered under CC0-1.0:
https://creativecommons.org/publicdomain/zero/1.0/

Run from `backend/`:

```bash
python -m app.benchmark --output benchmarks/results.json
```

The runner always creates a temporary isolated SQLite database and calls the production
trust scorer. It never uses `DATABASE_URL` or modifies application data. Exit status is 1
if any expected review decision differs from the measured decision.

The positive class is **requires expert review**, not polluted water, fraud, or an
incorrect report. An unusual but genuine measurement should be reviewed. A plausible
report of sewage smell can be trustworthy while describing concerning conditions.

`live_fixture` represents stipulated comparison evidence inserted only into the temporary
benchmark database to exercise the live-evidence branch. There are no real photos,
external AI calls, or measured model predictions. Such fixture outputs must never be
inserted into a real application database as live analysis.

`results.json` records the actual run: 14 true positives, 8 true negatives, 0 false
positives, and 0 false negatives. Precision/recall/accuracy are 1.0 on these authored
scenarios only. This measures agreement with a small policy regression set designed
alongside the scorer. It does not demonstrate generalization, vision accuracy, scientific
validity, fairness, or performance on an independent held-out dataset.

To extend the public test set, add independently labelled cases with provenance and
licensed images, retain a held-out evaluation split, and report its results separately.
No real volunteer records or external photo licenses are included in this dataset.
