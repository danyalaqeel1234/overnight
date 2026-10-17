#!/bin/bash
set -e

echo "=== Running NaSCon '26 Automated Verification & Coverage Suite ==="
python -m pytest --cov=app --cov-report=term --cov-report=json:coverage.json tests/
python scripts/generate_coverage_json.py
echo "=== Test Suite Completed Successfully ==="
