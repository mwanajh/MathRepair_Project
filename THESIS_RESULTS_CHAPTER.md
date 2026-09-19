# MathRepair Research Results

## 1. Research Question

This study asks whether verifier-guided local repair can recover errors in
model-generated mathematical reasoning more effectively than regenerating the
whole solution. The comparison is:

- **No repair:** keep the model's original chain.
- **Verified global regeneration:** ask the model for a new solution after an
  error is detected.
- **Verified local repair:** preserve the verified prefix, replace the first
  invalid step, and verify the repaired suffix.

The verifier is symbolic and checks equation transformations and answer
equivalence. A candidate repair is accepted only when the resulting chain
passes verification.

## 2. Primary Protocol

The primary comparison uses `qwen2-math:1.5b`, 36 expanded held-out problems,
three base seeds (`160500`, `180500`, `200500`), one sample per problem, and
temperature `1.4`. Each strategy receives a matched per-error computation
budget. The three trials produce 108 planned runs. Generation failures remain
in the denominator.

## 3. Primary Result

| Strategy | Answer accuracy | Valid traces |
|---|---:|---:|
| No repair | 90.7% | 88.0% |
| Global regeneration | 92.6% | 92.6% |
| Local repair | 100.0% | 100.0% |

Local repair exceeded global regeneration by `+7.4` percentage points for
both answer accuracy and trace validity. The paired 95% interval was
`[+3.4, +11.4]` percentage points. All matched-budget comparisons were valid.

This supports the engineering hypothesis that preserving verified context and
repairing only the invalid region is more effective than discarding the whole
chain for this algebra setting.

## 4. Model Comparison and Output Contract

The larger candidate models were evaluated on the same problems and seeds.

| Model / protocol | No repair | Global regeneration | Local repair |
|---|---:|---:|---:|
| `qwen2-math:1.5b` primary | 90.7% | 92.6% | 100.0% |
| `qwen2.5:3b` primary | 47.2% | 56.5% | 48.1% |
| `qwen2-math:7b` primary | 13.0% | 13.9% | 13.0% |
| `qwen2-math:7b` JSON profile | 75.0% | 75.9% | 85.2% |

The primary 7B run had `91/108` generation failures. An opt-in
`qwen2_math_json` prompt/parser profile reduced this to `10/108` by requesting
JSON mode, plain ASCII equations, and filtering explanatory entries inside
the `steps` array. This shows that the original 7B result was strongly
affected by output-contract incompatibility.

However, the profile remained below the 1.5B baseline by `15.7` percentage
points for no repair, `16.7` for global regeneration, and `14.8` for local
repair. Parser-normalized sensitivity reached `79.6%` answer accuracy, still
below the baseline. Therefore formatting explains a large part of the gap,
but not all of it.

Within the profile, local repair exceeded global regeneration by `+9.3`
percentage points, with a paired 95% interval of `[+5.3, +13.2]`.

## 5. Residual Failure Analysis

The profile is strongest on rational equations (`94.4%` no-repair accuracy),
nested subtraction (`91.7%`), and large coefficients (`91.7%`). Its weakest
categories are cubic transformations (`33.3%`) and large fractions (`38.9%`).
Local repair raises large-fraction accuracy to `77.8%` and nested-distribution
accuracy to `91.7%`.

Across completed profile runs, the typed analyzer found 15
algebraic-transformation errors and 1 arithmetic error. Model repair accepted
11 of 16 repair runs, corrected 11 wrong answers, and produced no answer
regressions. Offline replay recovered 5 of the 10 generation failures as
valid traces; the remaining 5 were parser failures.

## 6. Interpretation

The primary evidence supports verified local repair as the strongest strategy
in the tested one-variable algebra setting. The result is not a claim that a
larger language model is intrinsically worse at mathematics. The model
comparison demonstrates that end-to-end evaluation also measures compatibility
between a model's output contract and the pipeline parser. The controlled 7B
profile separates these effects and shows that both format incompatibility and
mathematical reasoning errors contribute to the observed gap.

## 7. Limitations

- The evaluation set contains 36 one-variable algebra problems and is not a
  public benchmark.
- Three repeated seeds provide a preliminary variance estimate, not a broad
  generalization guarantee.
- The primary result uses a small local model and a symbolic verifier.
- Trials reuse the same problems, so confidence intervals describe seed
  variation rather than problem-sampling uncertainty.
- Parser-normalized and model-specific profile results are sensitivity
  analyses; they do not replace the frozen primary protocol.

## 8. Reproducibility Artifacts

- Primary aggregate: `expanded_heldout_model_problems_repeated_experiments/aggregate_report.md`
- 3B comparison: `expanded_heldout_model_problems_repeated_experiments_qwen2.5_3b/aggregate_report.md`
- 7B primary comparison: `expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b/model_comparison.md`
- 7B JSON profile: `expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/aggregate_report.md`
- 7B failure replay: `expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/failure_replay_report.md`
