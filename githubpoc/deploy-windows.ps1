# Deploy from a path without spaces (Windows AgentCore CLI bug)

# AgentCore joins `uv` args with spaces and shell:true on Windows, so
# `C:\Users\Prajwal Nivangune\...` splits and synth fails on pyproject.toml.
# Deploy via this junction instead of Desktop\test\githubpoc.

$ErrorActionPreference = "Stop"
$junction = "C:\ac-githubpoc"
$target = "C:\Users\Prajwal Nivangune\Desktop\test\githubpoc"

if (-not (Test-Path $junction)) {
    New-Item -ItemType Junction -Path $junction -Target $target | Out-Null
    Write-Host "Created junction $junction -> $target"
}

Set-Location $junction
agentcore deploy -y --target default @args
