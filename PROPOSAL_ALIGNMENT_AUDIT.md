# Proposal Alignment Audit

Source reviewed: `C:\Users\mwana\Desktop\MarthRepair Summary.docx`

## Overall Status

**The full experiment described in the proposal is not complete.** The current
project has completed a reproducible pilot and feasibility evaluation for a
narrow one-variable algebra scope. This is appropriate as an early milestone,
but it is not yet the proposal's full benchmark, ablation, training, or
adaptive-compute study.

The proposal timeline places the current date (September 2026) in Phase 1:
literature review, formalization, graph definition, error taxonomy, and model
selection. Full benchmark experiments are scheduled later in the proposal.

## Research Questions

| Proposal question | Status | Evidence / gap |
|---|---|---|
| RQ1: graph representation localizes reasoning state | **Prototype complete; validation pending** | A working dependency-graph construction and branching demo exist. The full model evaluation still operates primarily on linear equation chains, and graph-based localization is not yet benchmarked against a flat baseline. |
| RQ2: typed verifier detects location and error category | **Partial** | Symbolic rule-based verification detects several algebra/arithmetic failures. A learned verifier, broad taxonomy, localization accuracy, and calibration study are not implemented. |
| RQ3: targeted repair beats generic correction | **Pilot complete** | Local repair, global regeneration, and no-repair were compared under matched budgets. The primary result favors local repair by `+7.4 pp`. |
| RQ4: node-level adaptive compute improves accuracy-efficiency | **Prototype only** | A heuristic allocator exists and has a demo report, but it is not integrated into the full benchmark comparison or evaluated with accuracy-compute Pareto curves. |

## Proposal Requirements

| Requirement | Status |
|---|---|
| MATH-500, AIME, OlympiadBench, or Omni-MATH evaluation | **Not complete**; current evaluation uses a custom 36-problem algebra set. |
| Eight listed baselines | **Not complete**; current comparison covers no repair, global regeneration, and local repair. |
| Final-answer and reasoning-trace metrics | **Complete for pilot scope**. |
| Error localization/type metrics | **Partial**; typed errors are reported, but no full classification benchmark or confusion analysis exists. |
| Repair success, false repair, calls, and tokens | **Complete for pilot scope**. |
| Confidence calibration and accuracy-compute Pareto curve | **Not complete**. |
| Component ablations | **Not complete**; no systematic removal of graph, typed verifier, repair policy, tool repair, or adaptive allocation. |
| Learned verifier/LoRA training | **Not complete**; current verifier and repair policy are symbolic/rule-based. |
| Controlled plus naturally occurring error dataset | **Partial**; synthetic/curated algebra problems and natural model traces exist, but no proposal-scale training dataset. |
| Full benchmark experiments and thesis-ready analysis | **Pilot analysis complete**; proposal-scale study remains. |

## What Is Complete Now

- Basic structured-reasoning and dependency-graph prototypes.
- Symbolic equation-chain verifier and typed repair decisions.
- Local repair implementation with verified prefix preservation.
- Matched-budget primary evaluation on 36 algebra problems and three seeds.
- 3B and 7B model comparisons, including a 7B output-contract sensitivity
  experiment.
- Parser, category, typed-error, failure-replay, thesis, and defense reports.

## Correct Research Claim At This Stage

The defensible claim is:

> In a controlled one-variable symbolic-algebra pilot, verified local repair
> outperformed verified global regeneration under a matched per-error budget.

The project cannot yet claim that the complete MathRepair framework improves
performance on MATH-500, AIME, OlympiadBench, or Omni-MATH, nor that node-level
adaptive compute has been empirically validated.

## Remaining Work For Full Proposal Completion

1. Freeze the graph, typed-error, and adaptive-compute specifications.
2. Build or select an evaluation set aligned with the proposal benchmarks.
3. Add the planned baselines and component ablations.
4. Integrate node-level adaptive allocation into the evaluated pipeline.
5. Report localization, classification, calibration, Pareto, and cost metrics.
6. Expand beyond one-variable algebra and repeat the primary comparison on
   independent problem sets.
