# MathRepair Typed-Error Taxonomy

This is the frozen vocabulary for verifier supervision. Error codes are stable
snake-case identifiers and must be used unchanged in traces, labels, reports,
and future learned-verifier targets.

The detector should apply the most specific rule first. In particular,
`sign_error` is a specialized diagnosis inside the broader family of invalid
algebraic transformations; it must be selected before
`algebraic_transformation_error`. A node receives one primary error type, while
its descendants are marked as affected by the graph.

| Error type | Definition | Positive example | Negative example | Detection contract | Recommended repair |
| --- | --- | --- | --- | --- | --- |
| `arithmetic_error` | A numerical calculation is incorrect while the intended operation and reasoning structure remain identifiable. | `45/5 = 8` when the value is 9. | `45/5 = 9`. | Parse and evaluate the arithmetic expression; flag a well-formed operation whose value is wrong. | `TOOL_EXECUTE`, then `LOCAL_RESAMPLE` if needed. |
| `algebraic_transformation_error` | An equation is changed by an invalid symbolic transformation, so the new state is not equivalent to its parent/problem. | `2(x + 3) = 14 -> 2x + 3 = 14`. | `2(x + 3) = 14 -> 2x + 6 = 14`. | Compare parsed parent/child identities or solution sets, after excluding arithmetic-only and sign-error cases. | `REFORMALIZE`, then `BACKTRACK`. |
| `sign_error` | A sign is changed incorrectly while moving a term, evaluating a coefficient, or reporting an isolated solution. | `x - 5 = 2 -> x = -3`; correct value is 7. | `x - 5 = 2 -> x = 7`. | Compare the proposed solution with the symbolic solution and run the sign-pattern predicate before the general algebra rule. | `BACKTRACK`, then `REFORMALIZE`. |
| `missing_assumption` | A step uses a domain, sign, nonzero, independence, or other condition not established by the problem or parents. | `x^2 = 9 -> x = 3` without `x >= 0`. | Given `x >= 0` and `x^2 = 9`, conclude `x = 3`. | Track assumptions in the graph and flag predicates required by a step but absent from the accumulated assumption set. | `BACKTRACK`, then `REPLAN`. |
| `logical_inference_error` | The conclusion does not follow from the parent premises even though the statements may be well-formed. | `n` even and `n` divides 6 -> `n = 2`. | `n` even and `n` divides 6 -> `n in {2, 6}`. | Run a logical entailment check over parent states and the proposed conclusion; a counterexample invalidates the node. | `BACKTRACK`, then `REPLAN`. |
| `semantic_interpretation_error` | The mathematical object, quantity, unit, quantifier, or condition in the problem is interpreted incorrectly. | Interpret “at least 3” as `x > 3`. | Interpret “at least 3” as `x >= 3`. | Normalize entities, units, and quantifiers from the problem and compare them with the formal reasoning state. | `REPLAN`, then `LOCAL_RESAMPLE`. |
| `dependency_error` | A node cites a missing, cyclic, or unverified parent, or applies a valid rule to the wrong preceding state. | `n3` depends on missing `n2`, or a cycle `n2 -> n3 -> n2`. | `n3` depends on verified `n2` and appears after it topologically. | Validate parent IDs, topological order, and parent final status before evaluating the child. | `BACKTRACK`, then `REPLAN`. |
| `incomplete_solution` | The trace stops before satisfying the requested goal, such as isolating the requested variable or stating the final set. | Stop at `2x = 8` when the task asks for `x`. | Continue with `2x = 8 -> x = 4`. | Check the final state against the requested target and require a complete answer form. | `REPLAN`, then `LOCAL_RESAMPLE`. |

## Scope And Operational Labels

The eight rows above are reasoning-error types intended as supervision targets.
The following labels describe pipeline failures and must not be mixed into the
reasoning-error distribution:

| Operational label | Meaning | Default handling |
| --- | --- | --- |
| `parser_failure` | The model response could not be converted into the requested trace format. | `LOCAL_RESAMPLE` |
| `unrecoverable_response_format` | No usable trace can be recovered after parser fallbacks. | `LOCAL_RESAMPLE` |
| `generation_error` | A repair-generation call failed before producing a candidate. | `LOCAL_RESAMPLE` |
| `unsupported_problem_type` / `text_unverified` | The current symbolic verifier does not cover the problem representation. | `REPLAN`; exclude from symbolic accuracy metrics. |

The empty error code means the node is verified and the repair action is
`CONTINUE`. Unknown future codes must default to `LOCAL_RESAMPLE` until this
document and `error_taxonomy.py` are updated together.

