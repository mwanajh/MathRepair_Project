# Thesis Abstract and Conclusion

## Abstract

Large language models can produce mathematically plausible reasoning chains
that contain a single invalid transformation and then propagate that error
through later steps. This study evaluates MathRepair, a verifier-guided repair
pipeline for one-variable symbolic algebra. The pipeline compares keeping a
model's original chain, regenerating a complete solution after an error, and
repairing only the first invalid region while preserving the verified prefix.
The symbolic verifier accepts a repair only when the resulting chain is
mathematically valid.

On an expanded held-out set of 36 algebra problems evaluated with three seeds,
the baseline `qwen2-math:1.5b` achieved 90.7% answer accuracy without repair,
92.6% with verified global regeneration, and 100.0% with verified local repair.
The paired local-minus-global advantage was 7.4 percentage points, with a 95%
interval of [3.4, 11.4]. These results support the hypothesis that preserving
verified context and repairing locally is more effective than discarding the
whole reasoning chain.

Experiments with larger models exposed an important evaluation confound. The
primary `qwen2-math:7b` run had 91 generation failures out of 108 because its
output frequently violated the parser's strict format contract. An opt-in
model-specific JSON prompt/parser profile reduced failures to 10/108 and
raised no-repair accuracy to 75.0%, but the result remained below the 1.5B
baseline. Thus output compatibility explains a substantial part of the
initial gap, while residual reasoning errors explain the remainder.

## Contributions

1. A symbolic verification pipeline that diagnoses invalid equation
   transformations and verifies proposed repairs.
2. A matched-budget comparison showing the benefit of verified local repair
   over global regeneration on the primary algebra evaluation.
3. A controlled analysis separating model reasoning quality from output-format
   compatibility.
4. A reproducible failure and category analysis identifying large fractions and
   cubic transformations as important residual weaknesses.

## Conclusion

The primary evidence supports verified local repair as the strongest of the
tested strategies for the evaluated one-variable algebra setting. The result
is specifically about repair under symbolic verification; it is not a claim
that the system solves general competition mathematics or that a smaller
language model is intrinsically more capable than a larger one.

The model-comparison experiments show why end-to-end evaluation must record
and control the output contract. A model can appear ineffective because its
mathematical output cannot be parsed, but correcting the contract does not
automatically close the performance gap. Both interface compatibility and
reasoning quality must therefore be reported separately.

## Future Work

- Extend the benchmark beyond one-variable algebra and increase the number of
  independent problem sets.
- Test prompt and parser profiles on additional model families under a frozen
  comparison protocol.
- Improve repair handling for large fractions and cubic transformations.
- Evaluate whether the verifier and repair policy generalize to multi-step
  proofs rather than equation solving alone.
