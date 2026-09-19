# Defense Questions and Evidence-Based Answers

## What is the central contribution?

The contribution is a verifier-guided local repair workflow. It does not ask
the model to be trusted at the final answer only. It verifies intermediate
equations, identifies the first invalid transformation, preserves the verified
prefix, and accepts a repair only after symbolic re-verification.

## Why compare local repair with global regeneration?

Global regeneration discards all previously generated reasoning. Local repair
tests whether verified context can be reused, reducing unnecessary changes and
allocating computation near the detected error. The primary comparison uses a
matched per-error budget so the strategies are comparable.

## Is 100% local-repair accuracy proof of general superiority?

No. It is the result on this 36-problem expanded set with three seeds. The
paired interval for local minus global excludes zero in this experiment, but
the task is small, synthetic/curated, and limited to one-variable algebra.

## Why did the 7B model perform so poorly at first?

The primary 7B run had 91 generation failures out of 108. Many responses were
valid-looking JSON but included prose or formatting that violated the strict
equation-only contract. The parser could not evaluate those runs, so the
primary result measured both reasoning and interface compatibility.

## Did the JSON profile solve the 7B problem?

It solved much of the interface problem, reducing failures to 10/108 and
raising no-repair accuracy from 13.0% to 75.0%. It did not close the gap to the
1.5B baseline, and parser-normalized accuracy was 79.6%. Therefore residual
mathematical reasoning errors remain.

## Why not replace the primary result with the normalized result?

The primary protocol must remain frozen for reproducibility. Parser-normalized
and model-specific results are sensitivity analyses that explain the primary
measurement; replacing the primary result would mix evaluation contracts.

## What are the main remaining weaknesses?

Large fractions and cubic transformations. Large-fraction accuracy improved
from 38.9% to 77.8% after local repair, while cubic transformation remained
low and also had the highest generation-failure rate in the profile.

## What would you do next scientifically?

Use independent problem sets and broader algebra categories, then evaluate
whether the same verifier-guided local-repair advantage holds outside the
current one-variable setting. Additional model runs should use a frozen
output contract and report parser failures separately.
