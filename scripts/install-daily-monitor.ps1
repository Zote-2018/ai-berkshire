<#
.SYNOPSIS
注册 AI-Berkshire-Daily-Monitor 到 Windows 任务计划程序（每个交易日 03:00）。

.DESCRIPTION
参考 commit 8a21858 的解决方案：用 schtasks（兼容 PS7）而非 Register-ScheduledTask，
避免 PowerShell 版本兼容问题。

任务名：AI-Berkshire-Daily-Monitor
触发：每周一至周五 03:00
动作：python tools/daily_monitor.py run
工作目录：脚本所在仓库根目录

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts/install-daily-monitor.ps1
#>

$ErrorActionPreference = "Stop"

$taskName = "AI-Berkshire-Daily-Monitor"
$repoRoot = Resolve-Path "$PSScriptRoot/.."
$python = (Get-Command python).Source
$workDir = $repoRoot.Path
$actionCmd = "`"$python`" `"$workDir\tools\daily_monitor.py`" run"

Write-Host "注册任务: $taskName"
Write-Host "  Python: $python"
Write-Host "  工作目录: $workDir"
Write-Host "  触发: 每周一至周五 03:00"

# schtasks 兼容 PS7（参考 commit 8a21858）
schtasks /Create /TN $taskName `
    /TR $actionCmd `
    /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 03:00 `
    /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] 任务已注册。手动触发测试：" -ForegroundColor Green
    Write-Host "   schtasks /run /tn `"$taskName`""
    Write-Host "查看任务状态："
    Write-Host "   schtasks /query /tn `"$taskName`" /v"
} else {
    Write-Host "[FAIL] 注册失败（exit code $LASTEXITCODE）" -ForegroundColor Red
    exit 1
}
