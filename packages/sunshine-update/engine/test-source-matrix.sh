#!/usr/bin/env bash
# G5 source-matrix proof. Every case has an explicit expected discovery shape
# and convergence plan in tests/source-matrix.toml.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m unittest tests.test_source_matrix -v

python3 - <<'PY'
import tomllib
from pathlib import Path

data = tomllib.loads(Path("tests/source-matrix.toml").read_text(encoding="utf-8"))
print("\nsource matrix:")
for case in data["cases"]:
    print("  {:30} {:<30} {}".format(
        case["fixture"], ",".join(case["axes"]), case["source_profile"]
    ))
print("axes:", ", ".join(sorted({a for c in data["cases"] for a in c["axes"]})))
print("source matrix: OK")
PY
