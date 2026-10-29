# FINHYPE: One-Command Pipeline Runner for PowerShell
[CmdletBinding()]
param(
    [switch]$Dashboard,
    [switch]$OnlyDashboard,
    [switch]$SkipBacktest,
    [switch]$SkipTests,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

if (Test-Path ".venv\Scripts\python.exe") {
    $python = ".venv\Scripts\python.exe"
} else {
    $python = "python"
}

$argsList = @("run_pipeline.py")

if ($Dashboard) { $argsList += "--dashboard" }
if ($OnlyDashboard) { $argsList += "--only-dashboard" }
if ($SkipBacktest) { $argsList += "--skip-backtest" }
if ($SkipTests) { $argsList += "--skip-tests" }

if ($RemainingArgs) {
    foreach ($arg in $RemainingArgs) {
        $argsList += $arg
    }
}

& $python $argsList
