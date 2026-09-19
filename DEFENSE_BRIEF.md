# MathRepair Defense Brief

## One-Sentence Claim

Verified local repair recovered more valid algebra reasoning than verified
global regeneration under the same per-error budget in the primary evaluation.

## Evidence To Present

| Primary strategy | Answer accuracy | Valid traces |
|---|---:|---:|
| No repair | 90.7% | 88.0% |
| Global regeneration | 92.6% | 92.6% |
| Local repair | 100.0% | 100.0% |

Local minus global: `+7.4 pp`, 95% CI `[+3.4, +11.4]`.

## Important Qualification

The primary model is `qwen2-math:1.5b`, the expanded set has 36 problems,
and three seeds produce 108 planned runs. This is evidence for the tested
one-variable algebra setting, not a general benchmark claim.

## How To Explain 7B

The first 7B run had `91/108` generation failures because the model often
returned explanatory entries, LaTeX, or other output that violated the strict
parser contract. A controlled JSON prompt/parser profile reduced failures to
`10/108` and raised no-repair accuracy to `75.0%`. It still remained below the
1.5B baseline, so formatting was a major factor but not the entire explanation.

## Contribution

MathRepair contributes a verifier-guided repair workflow: verify each step,
locate the first invalid transformation, preserve the valid prefix, repair the
affected suffix, and verify the result again.

The proposed-method graph construction is demonstrated separately in
[PROPOSED_METHOD_DEMO.md](PROPOSED_METHOD_DEMO.md). It shows branches,
dependencies, affected descendants, repair targeting, and adaptive allocation.

## Demo Sequence

```powershell
python mathrepair_demo.py
python model_pipeline.py --provider mock
python reasoning_graph.py
python allocation_report.py
python run_repeated_experiments.py --aggregate-only --problems expanded_heldout_model_problems.csv --seeds 160500 180500 200500 --samples-per-problem 1
```

The commands above use saved reports or the offline mock where appropriate;
they do not start new GPU evaluation runs.
