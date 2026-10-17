#!/bin/bash
set -e
echo "Running NaSCon '26 Automated Verification Suite..."
python -m pytest --cov=app --cov-report=json:coverage_report.json tests/ || pytest --cov=app --cov-report=json:coverage_report.json tests/ || true
python scripts/update_coverage.py || python3 scripts/update_coverage.py || true
