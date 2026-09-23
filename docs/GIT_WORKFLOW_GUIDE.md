# Git Workflow Guide for Poliwise

## What Just Happened

Your local branch `fix/bugfixes-and-tests` was **32 commits behind** `origin/main`. This happened because:
- Other branches merged to `main` while you worked locally
- Your local changes were uncommitted (in working directory)

## What We Did to Fix It

1. Created backup branch: `backup/pre-crisis-work`
2. Stashed modified files temporarily
3. Merged `origin/main` into your branch (fast-forward)
4. Frontend builds successfully ✓

---

## Safe Git Workflow (Recommended)

### Rule 1: Always Start with Sync

```bash
# Before ANY work session
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### Rule 2: Commit Early, Commit Often

```bash
# Make small, logical commits
git add path/to/changed-file.js
git commit -m "fix: handle null user profile gracefully"

# Or stage all changes
git add -A
git commit -m "feat: add document versioning support"
```

### Rule 3: Sync Main INTO Your Branch Daily

```bash
# While on your feature branch
git fetch origin
git merge origin/main

# Resolve conflicts immediately if any
# Then test and continue working
```

### Rule 4: Never Work Without a Branch

```
MAIN (protected, production-ready)
   ↓
feature/your-feature-name  ← YOU WORK HERE
   ↓
   PR → Code Review → Merge to main
```

### Rule 5: Backup Before Risky Operations

```bash
# Before major refactors or merges
git branch backup/before-refactor

# Before merging main into your branch
git stash push -m "Work in progress - merging main"
```

---

## Recovery Commands Reference

### Recovering Uncommitted Work

```bash
# List all stashes
git stash list

# Apply a specific stash
git stash apply stash@{0}

# Or pop the most recent
git stash pop
```

### Viewing What Changed

```bash
# See unstaged changes
git diff

# See staged changes
git diff --cached

# See commits unique to current branch
git log origin/main..HEAD --oneline
```

### Resetting to a Known Good State

```bash
# Keep local changes, reset to main
git reset --hard origin/main

# WARNING: This destroys uncommitted changes
git reset --hard origin/main
git clean -fd
```

---

## Your Current State

| Item | Value |
|------|-------|
| Current branch | `fix/bugfixes-and-tests` |
| HEAD | `de34d3e` (synced with origin/main) |
| Backup branch | `backup/pre-crisis-work` |
| Stashed changes | 1 stash (lock file changes) |

---

## Next Steps

1. **Review your untracked files** - These contain your local work:
   - `base_dataset/` - test documents
   - `contexts/` - documentation
   - `reports/` - analysis reports
   - `seed_data*.sql` - database seeds

2. **Decide what to do with them:**
   ```bash
   # Option A: Commit the useful ones
   git add base_dataset/
   git commit -m "docs: add base dataset for testing"

   # Option B: Keep them in .gitignore if temporary
   # Or delete if no longer needed
   ```

3. **Push your updated branch:**
   ```bash
   git push origin fix/bugfixes-and-tests
   ```

---

## Git Branch Strategy

```
origin/main ────────────────────────────────────────────► (production)
                 ↘
                  ↘ PR #15
                   ↘ fix/audited-security-and-logic ──────► merge
                              ↘ PR #16
                               ↘ fix/p0-p1-security ────────► merge
                                        ↘
                                         ↘ fix/bugfixes-and-tests ← YOU ARE HERE
                                            (now synced with main)
```

---

## Common Mistakes to Avoid

1. **Don't work directly on `main`** - Always create feature branches
2. **Don't skip `git pull` before starting work** - Sync first
3. **Don't let uncommitted work pile up** - Commit frequently
4. **Don't push without testing** - Build and verify first
5. **Don't skip the backup branch** - Before risky operations
