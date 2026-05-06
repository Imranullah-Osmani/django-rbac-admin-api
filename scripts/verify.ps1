Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [string]$Label,
        [string]$Command,
        [string[]]$Arguments
    )

    Write-Host $Label
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

Invoke-CheckedCommand "Checking Docker Compose config..." "docker" @("compose", "config", "--quiet")
Invoke-CheckedCommand "Running Django system checks..." "python" @("manage.py", "check")
Invoke-CheckedCommand "Checking migration drift..." "python" @("manage.py", "makemigrations", "--check", "--dry-run")
Invoke-CheckedCommand "Running test suite..." "python" @("manage.py", "test", "accounts.tests", "organizations.tests", "config.tests")

Write-Host "Django RBAC verification completed successfully."
