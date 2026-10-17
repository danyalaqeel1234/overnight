# NaSCon '26 Automated Verification Suite Runner (PowerShell)
Write-Host "Running NaSCon '26 Automated Verification Suite..." -ForegroundColor Cyan
python -m pytest --cov=app --cov-report=json:coverage_report.json tests/ -v
python scripts/update_coverage.py
