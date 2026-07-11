# scripts/run-scheduled-task.ps1
# Windows 任务计划程序的实际入口：被计划程序拉起后，切到 repo 跑 python -m tools.scheduler。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/run-scheduled-task.ps1 -Skill portfolio-review
#   powershell -ExecutionPolicy Bypass -File scripts/run-scheduled-task.ps1 -Skill industry-funnel

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("portfolio-review", "industry-funnel")]
    [string]$Skill,

    [string]$RepoRoot = "C:\workspace\ai-berkshire"
)

$ErrorActionPreference = "Stop"
$LogLevel = @{ INFO = "INFO"; WARN = "WARN"; ERROR = "ERROR" }

function Write-Log {
    param([string]$Level, [string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] [$Level] $Message"
}

# 切到 repo（python -m tools.scheduler 依赖 cwd）
try {
    Set-Location $RepoRoot
} catch {
    Write-Log ERROR "无法切到 $RepoRoot : $_"
    exit 2
}

Write-Log INFO "启动调度任务: $Skill（cwd=$RepoRoot）"

# 找 python（Windows 默认 python.exe，不是 python3）
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Log ERROR "找不到 python 可执行文件"
    exit 2
}

# industry-funnel 走 --from-queue；portfolio-review 不需要额外参数
$argList = @("-m", "tools.scheduler", $Skill)
if ($Skill -eq "industry-funnel") {
    $argList += @("--from-queue")
}

# 调外部命令时把 ErrorActionPreference 切到 Continue：python 写 stderr（_emit 日志）不能被
# 当作 PowerShell 异常抛进 catch（"$ErrorActionPreference=Stop" + 外部命令 stderr 经典坑）。
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & python @argList
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    if ($exitCode -ne 0) {
        Write-Log ERROR "$Skill 失败，exit=$exitCode"
        exit $exitCode
    }
    Write-Log INFO "$Skill 成功完成"
    exit 0
} catch {
    $ErrorActionPreference = $prevEAP
    Write-Log ERROR "调度异常: $_"
    exit 1
}
