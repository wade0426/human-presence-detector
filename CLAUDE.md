# CLAUDE.md

> This file follows AGENTS.md. If an AI needs to change CLAUDE.md, edit AGENTS.md instead, then rerun sync-claude-md.bat.

---

# AGENTS.md

This document provides guidelines for AI agents (such as Claude Code, Codex, Gemini CLI, etc.) when working on code in this repository.

> **Single source of truth.** Do **NOT** edit `CLAUDE.md` directly — that file is automatically generated from this document using synchronization scripts (`sync-claude-md.bat` for Windows, `sync-claude-md.sh` for Linux/macOS). Please make your modifications here and rerun the corresponding script.

---

## RTK Command Guidelines

When executing shell commands, prefer using RTK-wrapped commands whenever RTK supports the underlying tool. RTK supports over 100 common development commands, providing agents with safer and more consistent outputs for file inspection, searching, Git, testing, linting, build tools, package managers, cloud CLIs, containers, logs, and network inspection.

Particularly use RTK for commands where the output might be long, cluttered, or better suited for summarization:

| Category | Preferred Examples |
| --- | --- |
| File / Search | `rtk ls .`, `rtk read AGENTS.md`, `rtk read src/core/config.py -l aggressive`, `rtk smart src/core/config.py`, `rtk find "*.py" .`, `rtk grep "pattern" .`, `rtk diff file1 file2` |
| Git | `rtk git status`, `rtk git log -n 10`, `rtk git diff`, `rtk git add AGENTS.md`, `rtk git commit -m "message"`, `rtk git push`, `rtk git pull` |
| GitHub CLI | `rtk gh pr list`, `rtk gh pr view 42`, `rtk gh issue list`, `rtk gh run list` |
| Testing | `rtk pytest`, `rtk pytest tests/unit/test_merge.py`, `rtk pytest tests/unit/test_merge.py::test_merge_pages_sorts_and_cleans`, `rtk test <cmd>`, `rtk err <cmd>` |
| Build / Lint / Type Check | `rtk ruff check .`, `rtk mypy src cli`, `rtk lint`, `rtk tsc`, `rtk cargo build`, `rtk cargo clippy` |
| Package Manager / Dependencies | `rtk pip list`, `rtk pip outdated`, `rtk pnpm list`, `rtk deps` |
| Docker / Kubernetes | `rtk docker ps`, `rtk docker images`, `rtk docker logs <container>`, `rtk docker compose ps`, `rtk kubectl pods`, `rtk kubectl logs <pod>` |
| Data / Logs / Network | `rtk json config.json`, `rtk env -f CGSRAG`, `rtk log app.log`, `rtk curl <url>`, `rtk wget <url>`, `rtk summary <long command>`, `rtk proxy <command>` |
| RTK Analysis | `rtk gain`, `rtk gain --graph`, `rtk gain --history`, `rtk discover`, `rtk discover --all --since 7`, `rtk session` |

If RTK does not support a specific command or interferes with an interactive workflow, use the system's native shell commands directly, ensuring they align with the conventions of the current operating system (e.g., using PowerShell/cmd on Windows; Bash/Zsh on Linux/Ubuntu). For quick edits to local files, continue to use the editing tools provided by the agent environment rather than using shell redirection.

## 1. Common Commands (Cross-platform Windows / Linux, conda environment)

```bash
# Testing / Linting / Type Checking (Development dependencies are included in requirements.txt)
rtk pytest                                # Run the full test suite
rtk pytest tests/unit/test_merge.py       # Run tests in a single file
rtk pytest tests/unit/test_merge.py::test_merge_pages_sorts_and_cleans   # Run a single test case
rtk ruff check .
rtk mypy src cli

# Regenerate CLAUDE.md after editing AGENTS.md
# Windows system:
.\sync-claude-md.bat
# Linux (Ubuntu) system:
./sync-claude-md.sh
```

> **Environment and System Prompt Note:**
> This project's development environment covers both Windows and Linux. Before executing underlying shell commands, agents should **first determine the current operating system environment** and use command syntax that conforms to that system's conventions (for example: when manipulating environment variables, use `$env:VAR` in Windows PowerShell, and `$VAR` or `export VAR` in Linux Bash).