---
name: version-device
description: Use when user asks to freeze/snapshot/version a device, promote a frozen line to main, or list/manage device versions.
---

# Version Device Skill

This skill standardizes device version lifecycle operations: line selection, freeze snapshots, promotion to `main`, and version-history queries.

## Trigger Guidance

Use this skill when user asks to:

- freeze / snapshot / version a device state,
- fix a stable baseline,
- promote/merge a frozen line into `main`,
- list or manage device versions.

## Branch and Tag Model

- Development lines use branches: `device/<device>/<line>`
- Freeze tags are line-scoped: `device/<device>/<line>/vX.Y.Z`
- Main releases use global per-device tags: `release/<device>/vA.B.C`

Line versions and release versions are intentionally separate.

## Workflow

1. On create/update request, determine target device and ask user once:
   - create a new line (and choose base ref), or
   - continue an existing line.
2. Create/switch line branch.
3. During development run quick checks as usual.
4. When user asks to freeze:
   - run freeze pipeline,
   - persist logs/metrics/artifacts,
   - create freeze commit + freeze tag,
   - update device version catalog in `main` (`promoted_to_main = false`).
5. Ask only one follow-up: promote to `main` now?
6. If user says yes:
   - merge line into `main`,
   - assign next release version,
   - create release tag,
   - update catalog entry (`promoted_to_main = true`).

## Tooling Commands

Start or switch line:

```bash
python scripts/start_device_line.py \
  --device <device_name> \
  --line <line_name> \
  --base-ref <main_or_tag_or_commit>
```

Freeze current line state:

```bash
python scripts/freeze_device_version.py \
  --device <device_name> \
  --line <line_name>
```

Promote frozen version to `main`:

```bash
python scripts/promote_device_version.py \
  --device <device_name> \
  --line <line_name> \
  --version <vX.Y.Z>
```

List all known versions and lines for a device:

```bash
python scripts/list_device_versions.py \
  --device <device_name>
```

When reporting to user, include:

- `line_branches`
- `freeze_tags`
- `release_tags`
- `version_index` (if non-null) and `version_index_source`

## Freeze Outputs

Freeze stores artifacts under:

- `devices/<device>/versions/<line>/<version>/manifest.json`
- `devices/<device>/versions/<line>/<version>/test-summary.json`
- `devices/<device>/versions/<line>/<version>/logs/`
- `devices/<device>/versions/<line>/<version>/metrics/`

Plus metadata:

- `devices/<device>/VERSION`
- `devices/<device>/CHANGELOG.md`

## Global Catalog

Single source of version visibility:

- `devices/<device>/VERSION_INDEX.json` (maintained on `main`)

It tracks both freeze and release status for each line version.
