@echo off
setlocal

chcp 65001 > nul

set "ROOT=%~dp0"
set "AGENTS=%ROOT%AGENTS.md"
set "CLAUDE=%ROOT%CLAUDE.md"

if not exist "%AGENTS%" (
  echo AGENTS.md not found: "%AGENTS%"
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$agents = Get-Content -Raw -Encoding UTF8 -LiteralPath $env:AGENTS;" ^
  "$notice = @('# CLAUDE.md', '', '> This file follows AGENTS.md. If an AI needs to change CLAUDE.md, edit AGENTS.md instead, then rerun sync-claude-md.bat.', '', '---', '', '');" ^
  "$content = ($notice -join [Environment]::NewLine) + $agents;" ^
  "[System.IO.File]::WriteAllText($env:CLAUDE, $content, [System.Text.UTF8Encoding]::new($false));"

if errorlevel 1 exit /b %errorlevel%

echo Created "%CLAUDE%" from "%AGENTS%".
