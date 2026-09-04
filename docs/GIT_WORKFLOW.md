# Git Workflow for ACK

## Where things stand (Sept 2026)
- Solo project, everything committed directly to `main`; recent history is mostly `"updated README.md"`.
- Local `.git` currently has a stale `index.lock` blocking every write operation (add/commit/checkout/pull/restore). This has to be cleared by hand before any step below will work:
  - PowerShell: `Remove-Item .git\index.lock`
  - CMD: `del .git\index.lock`
  - If it says the file is in use, close Android Studio first (its VCS integration can hold a handle on it), then retry.
- There are ~47 files showing as modified that are line-ending noise only (CRLF vs LF), not real changes — most likely an editor re-save. Once the lock is clear:
  ```
  git status              # confirm what's dirty
  git restore .           # discard the line-ending-only noise (the .gitattributes fix below stops this recurring)
  git pull                # local main is currently 2 commits behind origin/main
  ```

## Recommended flow: short-lived feature branches (a.k.a. GitHub Flow)
Not full Gitflow (develop/release/hotfix branches) — that's built for release trains and multiple contributors, and is overkill for a solo app with one deployable target. The lightweight version:

1. `main` stays in a working, buildable state at all times.
2. Every piece of work — a fix, a new tutorial module, a UI tweak — gets its own short-lived branch off `main`.
3. Work happens there, in small focused commits.
4. When it's done and builds, merge back into `main` — locally, or via a GitHub pull request (recommended even solo: it's a free diff review and changelog).
5. Delete the branch.

## Day-to-day commands
```
git checkout main
git pull
git checkout -b feature/tutorial-help-registry-wiring   # name describes the change

# ...make edits...

git status                                               # see what actually changed
git add app/src/main/java/com/example/besu/HelpRegistry.kt   # stage only what you mean to commit
git commit -m "Wire Logs help module; dedupe basics-nav/geo-protocol help content"

git push -u origin feature/tutorial-help-registry-wiring
# open a PR on GitHub, or merge locally:
git checkout main
git merge --ff-only feature/tutorial-help-registry-wiring
git push
git branch -d feature/tutorial-help-registry-wiring
```

## Branch naming
- `feature/...` — new functionality
- `fix/...` — bug fixes
- `chore/...` — cleanup, tooling, docs

## Commit messages
Short imperative summary line (under ~70 chars); blank line; then the *why* if it isn't obvious from the diff. `"Wire Logs help module"`, not `"updated HelpRegistry.kt"`.

## Fixing the line-ending churn permanently
Add a `.gitattributes` file at the repo root:
```
* text=auto eol=lf
*.bat text eol=crlf
```
This normalizes line endings to LF in the repository regardless of what Android Studio/Windows saves locally (except `.bat` files, which need CRLF). Commit it once, then run `git add --renormalize .` to apply it to everything already tracked in one clean commit — after that, editor re-saves stop generating whole-repo noise diffs.

## Applying this to the current change
1. Clear the lock, then `git restore .` + `git pull` to get a clean, up-to-date `main`.
2. `git checkout -b feature/help-registry-wiring`
3. The `HelpRegistry.kt` edit is already sitting in the working tree — uncommitted changes aren't tied to a branch until committed, so they carry over onto the new branch automatically.
4. Review with `git diff`, then stage and commit just that file.
5. Push, open a PR (or fast-forward merge locally), merge, delete the branch.
