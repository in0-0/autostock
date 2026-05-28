---
description: "Releases AutoStock versions by synchronizing STATUS, ROADMAP, HISTORY, tags, and GitHub release notes. Triggers: release, publish version"
---

# Release

## Preconditions

- `python3 -m pytest` passes.
- Runtime smoke check passes or environment limitation is documented.
- No generated artifacts or secrets are staged.
- PR is approved and ready to merge.

## Document Synchronization

### `docs/STATUS.md`

Keep present state only:
- Last updated date
- current version and release status
- compact version plan
- health table
- one latest change
- next up

### `docs/ROADMAP.md`

Keep future plans only:
- remove completed version details after release
- move details into `docs/HISTORY.md`
- mark the next version

### `docs/HISTORY.md`

Add the released version at the top:

```markdown
## vX.Y.Z (YYYY-MM-DD) - PR #NNN

<one-line release summary>

### Changes
| Change | Details |
|--------|---------|
| ... | ... |

---
```

### `README.md`

Update only if the overview, commands, or version badge changed.

## GitHub Release

```bash
git tag -a vX.Y.Z -m "vX.Y.Z Release"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <notes.md>
```

## Final Checklist

- [ ] `python3 -m pytest`
- [ ] docs synchronized
- [ ] tag created
- [ ] GitHub release created
- [ ] related issues closed or linked
