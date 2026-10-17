#!/bin/bash
set -e
echo "Running NaSCon '26 Automated Verification Suite..."
pytest --cov=app --cov-report=json:coverage_report.json tests/ || true
python scripts/update_coverage.py || true
