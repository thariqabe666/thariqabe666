# Local stand-in for .github/workflows/update-profile.yml: re-render the bento
# tiles (activity + latest Substack posts), then commit and push any change.
# Scheduled daily via Windows Task Scheduler (task "Update GitHub profile tiles").

$ErrorActionPreference = 'Stop'
$Repo   = Split-Path -Parent $PSScriptRoot
$Python = 'C:\Azerbaijan_Intelligence\python.exe'
$Gh     = 'C:\Program Files\GitHub CLI\gh.exe'
$Git    = 'C:\Program Files\Git\cmd\git.exe'
$Log    = Join-Path $env:LOCALAPPDATA 'profile-tiles\update.log'

New-Item -ItemType Directory -Force (Split-Path $Log) | Out-Null
Start-Transcript -Path $Log -Append | Out-Null
try {
    Set-Location $Repo
    & $Git pull --rebase --autostash origin main
    if ($LASTEXITCODE) { throw "git pull failed ($LASTEXITCODE)" }

    $env:GH_TOKEN = (& $Gh auth token).Trim()
    & $Python scripts\bento.py --user thariqabe666
    if ($LASTEXITCODE) { throw "bento.py failed ($LASTEXITCODE)" }
    Remove-Item -Recurse -Force scripts\__pycache__ -ErrorAction SilentlyContinue

    & $Git add assets/tiles/*.svg
    & $Git diff --cached --quiet
    if ($LASTEXITCODE) {
        & $Git commit -m 'chore: refresh profile tiles'
        if ($LASTEXITCODE) { throw "git commit failed ($LASTEXITCODE)" }
    } else {
        Write-Output 'Tiles unchanged; nothing to commit.'
    }
    & $Git push origin main
    if ($LASTEXITCODE) { throw "git push failed ($LASTEXITCODE)" }
    Write-Output "Done $(Get-Date -Format s)"
} finally {
    Stop-Transcript | Out-Null
}
