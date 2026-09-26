"""Reproducible evaluation runner.

Runs the full eval suite (deterministic trajectory checks + LLM-judged
metrics), writes a structured JSON report to evals/results/, and exits
non-zero on any failure — suitable for CI.

    python -m evals.run_evals            # all evals
    python -m evals.run_evals --quick    # trajectory only (no judge calls)
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="skip LLM-judge evals")
    args = parser.parse_args()

    from evals.llm_judge import eval_judged
    from evals.trajectory_eval import eval_trajectory, load_cases

    cases = load_cases()
    started = time.time()
    results = []

    for case in cases:
        print(f"→ {case['id']}: {case['name']}", flush=True)
        try:
            if case["type"] == "judge":
                r = eval_judged(case) if not args.quick else {"passed": True, "skipped": "quick mode", "id": case["id"], "name": case["name"]}
            else:
                r = eval_trajectory(case)
        except Exception as exc:  # evals must report failures, not crash
            r = {
                "id": case["id"],
                "name": case["name"],
                "passed": False,
                "failures": [f"eval raised: {exc}"],
            }
        results.append(r)
        print(f"   {'PASS' if r['passed'] else 'FAIL'}"
              + (f" — {r.get('failures')}" if not r["passed"] else ""))

    passed = sum(1 for r in results if r["passed"])
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "duration_s": round(time.time() - started, 1),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"eval_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2))
    (RESULTS_DIR / "latest.json").write_text(json.dumps(report, indent=2))

    print(f"\n{passed}/{len(results)} evals passed — report: {out}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
