<#
.SYNOPSIS
    Registers a Windows Task Scheduler job to run Horse Havoc daily at 12:00 PM.
.DESCRIPTION
    Creates or updates the scheduled task "HorseHavoc_Daily_Pipeline" to execute
    run_pipeline.py every day at exactly 12:00.
#>

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
if (-not $ProjectDir) {
    $ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$PythonExe = (Get-Command python.exe).Source
if (-not $PythonExe) {
    $PythonExe = "python.exe"
}

$ScriptPath = Join-Path $ProjectDir "run_pipeline.py"
$TaskName = "HorseHavoc_Daily_Pipeline"
$RunTime = "12:00"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " [HORSE HAVOC] WINDOWS TASK SCHEDULER SETUP" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " * Task Name   : $TaskName"
Write-Host " * Schedule    : Daily at $RunTime"
Write-Host " * Python Path : $PythonExe"
Write-Host " * Script Path : $ScriptPath"
Write-Host " * Working Dir : $ProjectDir"
Write-Host "----------------------------------------------------------------------"

# Build execution command with working directory
$TaskCommand = "`"$PythonExe`" `"$ScriptPath`""

# Register task using Windows built-in schtasks
$schtasksArgs = @(
    "/Create",
    "/SC", "DAILY",
    "/TN", $TaskName,
    "/TR", $TaskCommand,
    "/ST", $RunTime,
    "/F"
)

try {
    & schtasks.exe $schtasksArgs
    Write-Host "`nSUCCESS: Windows Scheduled Task '$TaskName' has been registered!" -ForegroundColor Green
    Write-Host "It will trigger automatically every day at $RunTime." -ForegroundColor Green
    Write-Host "`nTo view task status:  schtasks /Query /TN `"$TaskName`""
    Write-Host "To run manually now:  schtasks /Run /TN `"$TaskName`""
    Write-Host "To delete task:       schtasks /Delete /TN `"$TaskName`" /F"
    Write-Host "======================================================================" -ForegroundColor Cyan
} catch {
    Write-Host "`n[!] Error registering task: $_" -ForegroundColor Red
}

