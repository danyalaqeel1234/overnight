"""Parse coverage.json (produced by pytest-cov) and write COVERAGE.json."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
COVERAGE_SRC = ROOT / "coverage.json"
COVERAGE_DEST = ROOT / "COVERAGE.json"

AREA_MODULES = {
    "fixtures":  ["app/domain/fixtures", "app/api/fixtures"],
    "scoring":   ["app/domain/scoring", "app/api/events"],
    "standings": ["app/domain/standings", "app/api/standings"],
    "store":     ["app/domain/store", "app/api/checkout"],
    "roster":    ["app/domain/roster", "app/api/roster"],
    "rbac":      ["app/core/security", "app/api/rbac"],
}


def _pct(hit: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(hit / total * 100, 1)


def main() -> None:
    if not COVERAGE_SRC.exists():
        print(f"coverage.json not found at {COVERAGE_SRC}", file=sys.stderr)
        result = {area: 0.0 for area in AREA_MODULES}
        COVERAGE_DEST.write_text(json.dumps(result, indent=2))
        return

    cov_data = json.loads(COVERAGE_SRC.read_text())
    files: dict = cov_data.get("files", {})

    result: dict[str, float] = {}
    for area, modules in AREA_MODULES.items():
        total_stmts = 0
        hit_stmts = 0
        for mod_prefix in modules:
            for path_str, file_data in files.items():
                # Normalise path separators
                norm = path_str.replace("\\", "/")
                if any(norm.endswith(m.replace("\\", "/") + ".py") or
                       mod_prefix.replace("\\", "/") in norm
                       for m in [mod_prefix]):
                    summary = file_data.get("summary", {})
                    total_stmts += summary.get("num_statements", 0)
                    hit_stmts += summary.get("covered_lines", 0)
        result[area] = _pct(hit_stmts, total_stmts)

    COVERAGE_DEST.write_text(json.dumps(result, indent=2))
    print("COVERAGE.json written:", result)


if __name__ == "__main__":
    main()
