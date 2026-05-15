# Codex Skills

This repository stores reusable Codex skills for team sharing.

## Install

Clone this repository, then copy the skills into your local Codex skills directory.

Windows PowerShell:

```powershell
.\scripts\install-skills.ps1
```

macOS/Linux:

```bash
./scripts/install-skills.sh
```

By default, all folders under `skills/` are copied to:

- Windows: `$env:USERPROFILE\.codex\skills`
- macOS/Linux: `$HOME/.codex/skills`

To install manually, copy each `skills/<skill-name>` folder into your local Codex skills directory.

## Layout

```text
README.md
scripts/
  install-skills.ps1
  install-skills.sh
skills/
  <skill-name>/
    SKILL.md
    references/
    scripts/
    assets/
```

Each skill must include `SKILL.md` with `name` and `description` frontmatter. Optional `references/`, `scripts/`, and `assets/` folders should be added only when the skill needs them.

## Adding Skills

Add each new skill as a separate folder under `skills/`.

```text
skills/my-new-skill/SKILL.md
```

Do not put README files inside individual skill folders. Keep human-facing repo documentation here, and keep each skill focused on the instructions Codex needs at runtime.

## Current Skills

- `regression-automation-tool`: Workflow guidance for adding APTIV regression issues and maintaining related Excel/config inputs.
