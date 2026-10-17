# Pre-commit verification script: blocks real .env files and secret tokens from being committed
$staged = git diff --cached --name-only
$hasErrors = $false

foreach ($file in $staged) {
    $baseName = Split-Path $file -Leaf
    if ($baseName -match '^\.env(\..+)?$' -and $baseName -ne '.env.example') {
        Write-Error "[PRE-COMMIT] Security violation: Staging real .env file detected ($file). Commit blocked."
        $hasErrors = $true
    }
}

if ($hasErrors) {
    exit 1
}

exit 0
