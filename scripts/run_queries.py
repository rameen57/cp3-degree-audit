"""Run CQ1-CQ8 and print the results.

Usage (from the project root):
    python scripts/run_queries.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit import queries  # noqa: E402


def main() -> None:
    print("Degree Audit ontology - competency question results")
    print("=" * 62)
    for result in queries.run_competency_questions():
        print(f"\n{result['id']}: {result['question']}")
        print(f"Expected: {result['expected']}")
        if not result["rows"]:
            print("Result:   (no rows)")
            continue
        for row in result["rows"]:
            print("Result:   " + " | ".join(row))
    print("\n" + "=" * 62)
    metrics = queries.get_ontology_metrics()
    print(
        "Measured metrics: "
        f"{metrics['classes']} classes, "
        f"{metrics['objectProperties']} object properties, "
        f"{metrics['dataProperties']} data properties, "
        f"{metrics['individuals']} individuals, "
        f"{metrics['triples']} triples"
    )


if __name__ == "__main__":
    main()
