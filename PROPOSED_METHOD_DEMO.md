# Proposed Method: Reasoning Graph Construction Demo

This artifact demonstrates the complete proposed-method loop on a small
branching equation example. It is a working proof-of-concept for the proposal
defense; large-benchmark integration remains future work.

## Method Flow

```text
Problem
  -> reasoning graph construction
  -> topological dependency ordering
  -> typed symbolic verification
  -> first-error localization
  -> affected-descendant tracing
  -> error-conditioned repair action
  -> node-level adaptive compute allocation
  -> repaired/final solution state
```

## Demonstration Graph

Problem: `2(x + 3) = 14`

| Node | Equation state | Depends on | Result |
|---|---|---|---|
| `n1` | `2x + 3 = 14` | problem | First algebraic error |
| `n2` | `2x = 11` | `n1` | Affected descendant |
| `n3` | `x = 5.5` | `n2` | Affected descendant |
| `n4` | `14 = 2(x + 3)` | problem | Unaffected branch |
| `n5` | `x = 4` | `n4` | Unaffected branch |

The graph demonstrates why a flat-chain repair is wasteful: the error in `n1`
propagates to `n2` and `n3`, while the independent `n4 -> n5` branch remains
valid.

## Observed Output

- First error: `n1`
- Error type: `algebraic_transformation_error`
- Suggested repair: `2x + 6 = 14`
- Affected nodes: `n2`, `n3`
- Unaffected nodes: `n4`, `n5`
- Repair action: `REFORMALIZE`
- Correct answer: `x = 4`
- Adaptive budget: `7` calls to `n1`, `2` to `n2`, `1` to `n3`, and `0` to
  unaffected nodes

## Run During Proposal Defense

From the project directory:

```powershell
python reasoning_graph.py
python allocation_report.py
```

The graph input is [reasoning_graph_example.json](reasoning_graph_example.json).
The implementation is [reasoning_graph.py](reasoning_graph.py), and the
allocation table is [allocation_report.md](allocation_report.md).

## Scope Statement

This demo establishes that graph construction, dependency-aware localization,
repair targeting, and heuristic allocation are implemented and observable.
The current model evaluation still uses linear equation traces; integrating
automatically generated model traces into richer branching graphs and testing
graph ablations on large benchmarks are proposal-level future work.
