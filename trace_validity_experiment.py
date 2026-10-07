"""Train and evaluate a trace-validity gate without using answer labels at inference."""

import argparse
import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from learned_verifier import load_examples, serialize_node, stratified_example_split


def trace_text(problem: str, trace: list[dict[str, object]]) -> str:
    return "\n---\n".join(
        serialize_node(problem, trace, index, include_graph=True)
        for index in range(len(trace))
    )


def clean_variants(problem: str, trace: list[dict[str, object]]) -> list[str]:
    """Create equivalent formatting variants of a valid trace."""
    base = trace_text(problem, trace)
    compact = "\n---\n".join(
        serialize_node(
            problem,
            [
                {**node, "state": " ".join(str(node.get("state", "")).split())}
                for node in trace
            ],
            index,
            include_graph=True,
        )
        for index in range(len(trace))
    )
    return [base, compact]


def rows(examples: list[dict[str, object]]) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    for example in examples:
        clean = clean_variants(str(example["problem"]), list(example["correct_trace"]))
        texts.extend(clean)
        texts.append(trace_text(str(example["problem"]), list(example["corrupted_trace"])))
        labels.extend([1] * len(clean) + [0])
    return texts, labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("typed_verifier_pilot.json"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    examples = load_examples(args.dataset)
    split = stratified_example_split(examples, args.seed)
    train_texts, train_labels = rows(split["train"])
    model = Pipeline(
        [
            ("features", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("classifier", LogisticRegression(max_iter=2000, random_state=args.seed)),
        ]
    ).fit(train_texts, train_labels)
    test_texts, test_labels = rows(split["test"])
    probabilities = model.predict_proba(test_texts)[:, 1]
    threshold_rows = []
    for threshold in (0.3, 0.4, 0.5, 0.6, 0.7):
        predictions = [int(value >= threshold) for value in probabilities]
        accuracy = sum(a == b for a, b in zip(test_labels, predictions)) / len(test_labels)
        clean_rejection = sum(
            value < threshold for value in probabilities[0::3]
        ) / len(probabilities[0::3])
        corrupted_detection = sum(
            value < threshold for value in probabilities[2::3]
        ) / len(probabilities[2::3])
        threshold_rows.append({
            "threshold": threshold,
            "pair_accuracy": accuracy,
            "clean_trace_rejection_rate": clean_rejection,
            "corrupted_trace_detection_rate": corrupted_detection,
        })
    print(json.dumps({
        "test_pair_count": len(split["test"]),
        "thresholds": threshold_rows,
        "interpretation": "A clean trace should be accepted; a corrupted trace should be rejected.",
    }, indent=2))


if __name__ == "__main__":
    main()
