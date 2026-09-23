"""Frozen typed-error taxonomy for MathRepair supervision and repair policy."""

from dataclasses import dataclass


ARITHMETIC_ERROR = "arithmetic_error"
ALGEBRAIC_TRANSFORMATION_ERROR = "algebraic_transformation_error"
SIGN_ERROR = "sign_error"
MISSING_ASSUMPTION = "missing_assumption"
LOGICAL_INFERENCE_ERROR = "logical_inference_error"
SEMANTIC_INTERPRETATION_ERROR = "semantic_interpretation_error"
DEPENDENCY_ERROR = "dependency_error"
INCOMPLETE_SOLUTION = "incomplete_solution"


@dataclass(frozen=True)
class ErrorTypeSpec:
    """One supervised reasoning-error class and its operational contract."""

    code: str
    definition: str
    positive_example: str
    negative_example: str
    detection: str
    recommended_actions: tuple[str, ...]


ERROR_TAXONOMY: dict[str, ErrorTypeSpec] = {
    ARITHMETIC_ERROR: ErrorTypeSpec(
        code=ARITHMETIC_ERROR,
        definition=(
            "A numerical calculation is incorrect while the intended operation "
            "and reasoning structure remain identifiable."
        ),
        positive_example="45/5 = 8 (the calculated value should be 9).",
        negative_example="45/5 = 9.",
        detection=(
            "Parse both sides and evaluate the arithmetic expression; classify "
            "the node when the operation is otherwise well-formed but values differ."
        ),
        recommended_actions=("TOOL_EXECUTE", "LOCAL_RESAMPLE"),
    ),
    ALGEBRAIC_TRANSFORMATION_ERROR: ErrorTypeSpec(
        code=ALGEBRAIC_TRANSFORMATION_ERROR,
        definition=(
            "An equation is changed by an invalid symbolic transformation, so "
            "the new state is not equivalent to its parent/problem."
        ),
        positive_example="2(x + 3) = 14 -> 2x + 3 = 14.",
        negative_example="2(x + 3) = 14 -> 2x + 6 = 14.",
        detection=(
            "Parse parent and child equations, compare their solution sets or "
            "identity, and exclude arithmetic-only and sign-error matches."
        ),
        recommended_actions=("REFORMALIZE", "BACKTRACK"),
    ),
    SIGN_ERROR: ErrorTypeSpec(
        code=SIGN_ERROR,
        definition=(
            "A sign is changed incorrectly while moving a term, evaluating a "
            "coefficient, or reporting the isolated solution."
        ),
        positive_example="x - 5 = 2 -> x = -3 (the correct value is 7).",
        negative_example="x - 5 = 2 -> x = 7.",
        detection=(
            "Compare the proposed solution with the symbolic solution and test "
            "the verifier's sign-pattern predicate before the general algebra rule."
        ),
        recommended_actions=("BACKTRACK", "REFORMALIZE"),
    ),
    MISSING_ASSUMPTION: ErrorTypeSpec(
        code=MISSING_ASSUMPTION,
        definition=(
            "A step uses a domain, sign, nonzero, independence, or other "
            "condition that has not been established by the problem or parents."
        ),
        positive_example="x^2 = 9 -> x = 3 without establishing x >= 0.",
        negative_example="Given x >= 0 and x^2 = 9 -> x = 3.",
        detection=(
            "Track assumptions in the graph; flag a conclusion whose proof "
            "requires a predicate absent from the accumulated assumption set."
        ),
        recommended_actions=("BACKTRACK", "REPLAN"),
    ),
    LOGICAL_INFERENCE_ERROR: ErrorTypeSpec(
        code=LOGICAL_INFERENCE_ERROR,
        definition=(
            "The conclusion does not follow from the parent premises even "
            "though the individual statements may be well-formed."
        ),
        positive_example=(
            "n is a positive even divisor of 6 -> n = 2 "
            "(n = 6 is also possible)."
        ),
        negative_example="n is a positive even divisor of 6 -> n in {2, 6}.",
        detection=(
            "Use a logical entailment check over parent states and the proposed "
            "conclusion; a counterexample makes the node invalid."
        ),
        recommended_actions=("BACKTRACK", "REPLAN"),
    ),
    SEMANTIC_INTERPRETATION_ERROR: ErrorTypeSpec(
        code=SEMANTIC_INTERPRETATION_ERROR,
        definition=(
            "The mathematical object, quantity, unit, quantifier, or condition "
            "in the problem is interpreted incorrectly."
        ),
        positive_example="'At least 3' interpreted as x > 3 instead of x >= 3.",
        negative_example="'At least 3' interpreted as x >= 3.",
        detection=(
            "Normalize entities, units, and quantifiers from the problem and "
            "compare them with the reasoning state's formal interpretation."
        ),
        recommended_actions=("REPLAN", "LOCAL_RESAMPLE"),
    ),
    DEPENDENCY_ERROR: ErrorTypeSpec(
        code=DEPENDENCY_ERROR,
        definition=(
            "A node cites a missing, cyclic, or unverified parent, or applies "
            "a valid rule to the wrong preceding state."
        ),
        positive_example="n3 depends on missing node n2 (or a cycle n2 -> n3 -> n2).",
        negative_example="n3 depends on verified n2 and appears after n2 topologically.",
        detection=(
            "Validate parent IDs, topological order, and parent final status before "
            "evaluating the child node."
        ),
        recommended_actions=("BACKTRACK", "REPLAN"),
    ),
    INCOMPLETE_SOLUTION: ErrorTypeSpec(
        code=INCOMPLETE_SOLUTION,
        definition=(
            "The trace stops before satisfying the requested goal, such as "
            "isolating the requested variable or stating the final set."
        ),
        positive_example="2x = 8 when the task asks for x and no final isolation follows.",
        negative_example="2x = 8 -> x = 4.",
        detection=(
            "Check the final state against the problem's requested target and "
            "require an isolated variable or complete answer form."
        ),
        recommended_actions=("REPLAN", "LOCAL_RESAMPLE"),
    ),
}


ERROR_TYPE_CODES = tuple(ERROR_TAXONOMY)


def get_error_spec(error_type: str) -> ErrorTypeSpec | None:
    """Return the frozen specification for a canonical error code."""
    return ERROR_TAXONOMY.get(error_type)
