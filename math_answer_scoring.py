"""Extract and score final answers from open-ended MATH benchmark traces."""

import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


TRANSFORMATIONS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)


def _last_braced_command(text: str, command: str) -> str | None:
    """Return the last balanced braced argument for a LaTeX command."""
    starts = [match.end() for match in re.finditer(re.escape(command) + r"\s*\{", text)]
    for content_start in reversed(starts):
        depth = 1
        for index in range(content_start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    return text[content_start:index]
    return None


def extract_final_answer(steps: list[str], raw_response: str = "") -> str:
    """Extract the final answer without using the benchmark reference answer."""
    candidates = list(steps)
    if raw_response:
        candidates.append(raw_response)
    combined = "\n".join(candidates)
    boxed = _last_braced_command(combined, r"\boxed")
    if boxed:
        return boxed.strip()
    patterns = (
        r"(?im)^\s*(?:final\s+answer|answer)\s*(?:is|:|=)\s*(.+?)\s*$",
        r"(?i)(?:final\s+answer|answer)\s*(?:is|:|=)\s*([^\n]+)",
    )
    for pattern in patterns:
        matches = re.findall(pattern, combined)
        if matches:
            return str(matches[-1]).strip()
    inline_math = re.findall(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$|\\\((.+?)\\\)", combined)
    if inline_math:
        left, right = inline_math[-1]
        return (left or right).strip()
    simplified = re.findall(
        r"(?i)(?:simplifies\s+to|equals)\s+([^.;\n]+)", combined
    )
    if simplified:
        return simplified[-1].strip()
    final_state = steps[-1].strip() if steps else ""
    if "=" in final_state:
        tail = final_state.rsplit("=", 1)[1].strip().rstrip(".\"'")
        if tail and len(tail) <= 100:
            return tail
    terminal_value = re.findall(
        r"(?i)(?:\bis|\bwas|\bbecomes)\s+"
        r"(\$?[-+]?\s*(?:\\frac\{[^{}]+\}\{[^{}]+\}|"
        r"\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?|"
        r"(?:\\?pi|π)(?:\s*/\s*\d+)?)\$?)\s*[.\"']*$",
        final_state,
    )
    if terminal_value:
        return terminal_value[-1].strip()
    return final_state


def _replace_latex_fractions(text: str) -> str:
    pattern = re.compile(r"\\(?:d)?frac\s*\{([^{}]+)\}\s*(?:\{([^{}]+)\}|([^\s]+))")
    previous = None
    while text != previous:
        previous = text
        text = pattern.sub(
            lambda match: f"(({match.group(1)})/({match.group(2) or match.group(3)}))",
            text,
        )
    return text


def normalize_answer_text(text: str) -> str:
    """Normalize common MATH answer formatting without decimal approximation."""
    value = text.strip()
    boxed = _last_braced_command(value, r"\boxed")
    if boxed:
        value = boxed
    value = re.sub(r"(?i)^\s*(?:therefore[, ]*)?(?:the\s+)?(?:final\s+)?answer\s*(?:is|:|=)?\s*", "", value)
    value = value.replace("\\left", "").replace("\\right", "")
    value = value.replace("\\dfrac", "\\frac")
    value = _replace_latex_fractions(value)
    value = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", value)
    value = re.sub(r"\\(?:text|mathrm)\s*\{[^{}]*\}", "", value)
    value = value.replace(r"\pi", "pi").replace("π", "pi")
    value = value.replace(r"\cdot", "*").replace(r"\times", "*")
    value = value.replace(r"\in", " in ").replace(r"\$", "")
    value = value.replace("°", "").replace(r"^\circ", "").replace(r"\circ", "")
    value = value.replace("$", "").replace(",", "")
    value = re.sub(r"(?i)\s*(?:degrees?|dollars?|cents?)\s*$", "", value)
    value = re.sub(r"(?i)^\s*[a-z][a-z0-9_]*\s+in\s+", "", value)
    value = re.sub(r"(?i)^\s*[a-z][a-z0-9_]*\s*=\s*", "", value)
    if "=" in value:
        value = value.rsplit("=", 1)[1]
    value = value.strip().rstrip(".。\"'")
    return "".join(value.split())


def _sympy_expression(text: str) -> sp.Expr:
    value = text.replace("i", "I")
    return parse_expr(
        value,
        local_dict={"pi": sp.pi, "I": sp.I, "sqrt": sp.sqrt},
        transformations=TRANSFORMATIONS,
        evaluate=True,
    )


def answers_equivalent(expected: str, actual: str) -> bool:
    """Compare exact scalar/symbolic answers, with normalized-text fallback."""
    expected_normalized = normalize_answer_text(expected)
    actual_normalized = normalize_answer_text(actual)
    if not expected_normalized or not actual_normalized:
        return False
    if expected_normalized.lower() == actual_normalized.lower():
        return True
    try:
        difference = sp.simplify(
            _sympy_expression(expected_normalized) - _sympy_expression(actual_normalized)
        )
        return difference == 0
    except Exception:
        return False
