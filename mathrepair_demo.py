"""A beginner-friendly, interactive MathRepair prototype."""

from dataclasses import dataclass
import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from repair_policy import make_repair_decision


TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)


@dataclass
class ReasoningNode:
    """One step in a reasoning graph."""

    node_id: str
    text: str
    depends_on: list[str]
    error_type: str | None = None


def verify_distribution() -> tuple[bool, str, str]:
    """Check whether 2(x + 3) was expanded correctly."""
    x = sp.Symbol("x")
    original_left = 2 * (x + 3)
    proposed_left = 2 * x + 3  # Deliberately incorrect model output.
    expected_left = sp.expand(original_left)

    if sp.simplify(proposed_left - expected_left) != 0:
        return False, "algebraic_transformation_error", str(expected_left)
    return True, "", str(proposed_left)


def parse_equation(text: str) -> sp.Equality:
    """Convert text such as '2(x + 3) = 14' into a SymPy equation."""
    if text.count("=") != 1:
        raise ValueError("Write an equation with exactly one '=' sign.")

    left_text, right_text = text.replace("^", "**").split("=")
    local_symbols = {letter: sp.Symbol(letter) for letter in "xyz"}
    left = parse_expr(
        left_text.strip(),
        local_dict=local_symbols,
        transformations=TRANSFORMATIONS,
    )
    right = parse_expr(
        right_text.strip(),
        local_dict=local_symbols,
        transformations=TRANSFORMATIONS,
    )
    return sp.Eq(left, right, evaluate=False)


def equation_variables(equation: sp.Equality) -> set[sp.Symbol]:
    """Return all variables used on both sides of an equation."""
    return equation.lhs.free_symbols | equation.rhs.free_symbols


def normalize_solution_set(solutions: sp.Set) -> sp.Set:
    """Make exact decimal and rational finite solutions comparable."""
    if not isinstance(solutions, sp.FiniteSet):
        return solutions
    return sp.FiniteSet(*(sp.nsimplify(value) for value in solutions))


def format_solution(variable: sp.Symbol, solutions: sp.Set) -> str:
    """Show a one-variable solution in a beginner-friendly form."""
    if isinstance(solutions, sp.FiniteSet) and len(solutions) == 1:
        value = next(iter(solutions))
        return f"{variable} = {value}"
    return f"{variable} in {solutions}"


def format_expression(expression: sp.Expr) -> str:
    """Format a SymPy expression for display, for example 3*x as 3x."""
    return re.sub(r"(?<=\d)\*(?=[A-Za-z])", "", str(expression))


def corrected_equation(equation: sp.Equality) -> str:
    """Create a clear equivalent step by expanding both sides."""
    left = format_expression(sp.expand(equation.lhs))
    right = format_expression(sp.expand(equation.rhs))
    return f"{left} = {right}"


def is_sign_error(
    original: sp.Equality,
    variable: sp.Symbol,
    original_solutions: sp.Set,
    proposed_solutions: sp.Set,
) -> bool:
    """Detect common sign mistakes in a one-variable linear equation."""
    if not (
        isinstance(original_solutions, sp.FiniteSet)
        and isinstance(proposed_solutions, sp.FiniteSet)
        and len(original_solutions) == 1
        and len(proposed_solutions) == 1
    ):
        return False

    correct_value = next(iter(original_solutions))
    proposed_value = next(iter(proposed_solutions))
    if proposed_value == -correct_value:
        return True

    if variable in original.rhs.free_symbols:
        return False

    try:
        left_polynomial = sp.Poly(sp.expand(original.lhs), variable)
    except sp.PolynomialError:
        return False
    if left_polynomial.degree() != 1:
        return False

    coefficient = left_polynomial.coeff_monomial(variable)
    constant = left_polynomial.coeff_monomial(1)
    wrong_sign_value = sp.simplify((original.rhs + constant) / coefficient)
    return proposed_value == wrong_sign_value and proposed_value != correct_value


def verify_user_step(
    original_text: str, proposed_text: str
) -> tuple[bool, str, str, str]:
    """Check whether a proposed equation has the same solutions as the original."""
    original = parse_equation(original_text)
    proposed = parse_equation(proposed_text)
    variables = equation_variables(original) | equation_variables(proposed)

    if len(variables) > 1:
        raise ValueError("Currently supports one variable only, for example x.")

    if not variables:
        original_true = sp.simplify(original.lhs - original.rhs) == 0
        proposed_true = sp.simplify(proposed.lhs - proposed.rhs) == 0
        ok = original_true == proposed_true
        answer = "true" if original_true else "false"
        error_type = "" if ok else "arithmetic_error"
        repair = original_text.strip()
        return ok, error_type, repair, answer

    variable = variables.pop()
    original_solutions = normalize_solution_set(
        sp.solveset(original, variable, domain=sp.S.Reals)
    )
    proposed_solutions = normalize_solution_set(
        sp.solveset(proposed, variable, domain=sp.S.Reals)
    )
    ok = original_solutions == proposed_solutions
    answer = format_solution(variable, original_solutions)
    if ok:
        error_type = ""
        repair = corrected_equation(original)
    elif is_sign_error(original, variable, original_solutions, proposed_solutions):
        error_type = "sign_error"
        repair = answer
    else:
        error_type = "algebraic_transformation_error"
        repair = corrected_equation(original)

    return ok, error_type, repair, answer


def verify_reasoning_step(
    problem_text: str, step_text: str
) -> tuple[bool, str, str, str]:
    """Verify a solution transformation or a supporting identity node."""
    problem = parse_equation(problem_text)
    step = parse_equation(step_text)
    _, _, _, answer = verify_user_step(problem_text, problem_text)

    if sp.simplify(step.lhs - step.rhs) == 0:
        return True, "", step_text.strip(), answer

    if equation_variables(problem) and not equation_variables(step):
        left_text = step_text.split("=", maxsplit=1)[0].strip()
        corrected_value = format_expression(sp.simplify(step.lhs))
        repair = f"{left_text} = {corrected_value}"
        return False, "arithmetic_error", repair, answer

    return verify_user_step(problem_text, step_text)


def repair_graph() -> list[ReasoningNode]:
    """Verify the bad node and repair that node without regenerating all steps."""
    nodes = [
        ReasoningNode("n1", "Problem: 2(x + 3) = 14", []),
        ReasoningNode("n2", "2x + 3 = 14", ["n1"]),
        ReasoningNode("n3", "2x = 11", ["n2"]),
        ReasoningNode("n4", "x = 5.5", ["n3"]),
    ]

    ok, error_type, corrected_left = verify_distribution()
    if not ok:
        nodes[1].error_type = error_type
        nodes[1].text = f"{corrected_left} = 14"
        # Downstream steps are recomputed after the repaired node.
        nodes[2].text = "2x = 8"
        nodes[3].text = "x = 4"
    return nodes


def main() -> None:
    print("=== MathRepair: interactive prototype ===")
    print("Enter the equation and the reasoning step you want MathRepair to verify.\n")

    original_text = input("Original equation: ").strip()
    proposed_text = input("Step to verify: ").strip()

    try:
        ok, error_type, repair, correct_answer = verify_user_step(
            original_text, proposed_text
        )
    except (ValueError, TypeError, SyntaxError) as error:
        print(f"\nINPUT ERROR: {error}")
        print("Example: 2(x + 3) = 14")
        return

    if ok:
        print("\nNO ERROR: This step is equivalent to the original equation.")
    else:
        print("\nERROR FOUND")
        print(f"Error type: {error_type}")
        decision = make_repair_decision(error_type, repair)
        print(f"Repair action: {decision.action.value}")
        print(f"Reason: {decision.reason}")
        print(f"Corrected step: {repair}")

    print(f"Correct answer: {correct_answer}")


if __name__ == "__main__":
    main()
