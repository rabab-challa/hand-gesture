# Git Workflow Guide

## How to Update GitHub After Making Changes

### Quick Steps:
1. **Check what changed:**
   ```bash
   git status
   ```

2. **Add your changes:**
   ```bash
   git add .                    # Add all changes
   # OR
   git add filename.py          # Add specific file
   ```

3. **Commit your changes:**
   ```bash
   git commit -m "Description of your changes"
   ```

4. ** Push to GitHub:**
   ```bash
   git push
   ```

### Example:
```bash
# Git Workflow Guide

## How to update GitHub after making local changes

This short guide shows the common commands and recommended steps to keep your local project and the GitHub repo in sync.

### Basic single-branch workflow
- Check current status and branch:
```powershell
git status
git branch --show-current
```

- Get latest remote changes before you start (recommended):
```powershell
git pull origin main
```

- Stage and commit your edits:
```powershell
git add .
git commit -m "Short, descriptive message"
```

- Push your commit to GitHub:
```powershell
git push origin main
# If this is the first push for the branch:
git push -u origin main
```

> Replace `main` with your branch name when applicable.

### Feature-branch workflow (recommended for new work)
- Create and switch to a new branch:
```powershell
git checkout -b feature/your-name
```

- Work, stage, and commit as usual:
```powershell
git add .
git commit -m "feat: short description"
```

- Push the branch and open a Pull Request on GitHub:
```powershell
git push -u origin feature/your-name
```

### Keeping your branch up to date and handling conflicts
- Pull and rebase the latest main before pushing:
```powershell
git pull --rebase origin main
```

- If you hit conflicts: edit the conflicted files, then:
```powershell
git add <file>
git rebase --continue
```
Or if you used merge:
```powershell
# resolve files, then
git add <file>
git commit
```

### If `origin` is not set or needs updating
```powershell
git remote add origin https://github.com/USERNAME/REPO.git
# or update an existing remote
git remote set-url origin https://github.com/USERNAME/REPO.git
```

### VS Code Source Control (GUI)
- Open the Source Control view (Ctrl+Shift+G), stage files, write a commit message, then click the push/pull icons.
- Sign in to GitHub when prompted to enable PRs and other integration features.

### Quick reference commands
- `git status` — show changed files
- `git diff` — view unstaged changes
- `git log --oneline --graph` — compact history
- `git branch -a` — list branches
- `git remote -v` — show remotes

### Notes
- Use Pull Requests (PRs) for code review and safer merges.
- Keep commit messages short and descriptive (imperative tense).

For more advanced workflows (CI, protected branches, or git hooks), add project-specific sections below.

