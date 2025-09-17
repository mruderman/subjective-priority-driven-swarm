# Git Workflow Guide

## Pull Strategy Configuration

This repository is configured with the following git settings:
- **Pull strategy**: Merge (preserves history, safe for collaboration)
- **Fast-forward**: Enabled when possible
- **Merge tool**: vimdiff

## Workflow Commands

### Quick Commands (Using Aliases)
```bash
# Start new feature
git new-feature feature/my-feature-name

# Switch branches 
git sw main
git sw feature/my-feature

# Sync main branch
git sync

# Clean up merged branches
git cleanup
```

### Standard Workflow

#### 1. Starting New Work
```bash
# Always start from updated main
git checkout main
git pull origin main
git checkout -b feature/descriptive-name
```

#### 2. Working on Features
```bash
# Make commits
git add .
git commit -m "Descriptive commit message"

# Push feature branch
git push origin feature/descriptive-name
```

#### 3. Merging Back to Main
**Use Pull Requests for all merges to main**

```bash
# Create PR via GitHub web interface or CLI
gh pr create --title "Feature: Description" --body "Details..."

# After PR approval and merge, clean up
git checkout main
git pull origin main
git branch -d feature/descriptive-name
```

## When to Merge to Main

### ✅ **Recommended Triggers for Merging:**

1. **Feature Complete**: A self-contained feature is fully implemented and tested
2. **Bug Fix**: Critical or high-priority bug fixes
3. **Documentation Updates**: Significant documentation improvements
4. **Refactoring**: Code improvements that don't change functionality
5. **Hotfixes**: Urgent production fixes

### ⏰ **Timing Guidelines:**

- **Small features**: Merge when complete (daily to weekly)
- **Large features**: Break into smaller pieces, merge incrementally
- **Bug fixes**: Merge ASAP after testing
- **Experimental work**: Only merge when stable and tested

### 🚫 **Avoid Merging:**

- Incomplete features that break existing functionality
- Work-in-progress commits
- Experimental code that's not tested
- Changes that would block other developers

## Branch Naming Conventions

```bash
feature/add-secretary-agent          # New features
bugfix/fix-memory-overflow          # Bug fixes  
hotfix/critical-security-patch      # Urgent fixes
docs/update-installation-guide      # Documentation
refactor/simplify-swarm-manager     # Code improvements
```

## Best Practices

### 🎯 **Golden Rules:**
1. **Never commit directly to main** - Always use feature branches
2. **Pull before starting new work** - Keep main updated
3. **Write descriptive commit messages** - Help future developers
4. **Test before merging** - Ensure code works
5. **Keep PRs focused** - One feature/fix per PR

### 🔄 **Daily Workflow:**
```bash
# Morning routine
git checkout main
git sync

# Start work
git new-feature feature/my-work

# During work
git add . && git commit -m "Progress on feature"
git push origin feature/my-work

# End of day
# Create PR if feature is complete
# Otherwise, continue tomorrow
```

### 🧹 **Weekly Cleanup:**
```bash
# Clean up merged branches
git cleanup

# Check for any stale branches
git branch -a
```

## Handling Conflicts

### During Pull:
```bash
# If conflicts occur during git pull
git status  # See conflicted files
# Edit files to resolve conflicts
git add .
git commit  # Complete the merge
```

### During PR Merge:
```bash
# If main has moved ahead
git checkout feature/my-branch
git pull origin main  # This will merge main into your feature
# Resolve any conflicts
git push origin feature/my-branch  # Update PR
```

## Emergency Procedures

### Undo Last Commit (Not Pushed):
```bash
git reset --soft HEAD~1  # Keep changes staged
git reset HEAD~1         # Keep changes unstaged
git reset --hard HEAD~1  # Discard changes completely
```

### Fix Pushed Commit:
```bash
git revert <commit-hash>  # Create new commit that undoes changes
```

### Force Sync (Last Resort):
```bash
git fetch origin
git reset --hard origin/main  # ⚠️ DESTROYS local changes
```

## Configuration Summary

The repository is configured with these settings:
```bash
pull.rebase = false    # Use merge strategy
pull.ff = true         # Allow fast-forward
merge.tool = vimdiff   # Default merge tool

# Useful aliases
sw = switch
co = checkout
sync = pull origin main
new-feature = "!f() { git checkout main && git pull origin main && git checkout -b \"$1\"; }; f"
cleanup = "!f() { git checkout main && git pull origin main && git branch --merged | grep -v \"\\*\\|main\\|master\" | xargs -n 1 git branch -d; }; f"
```