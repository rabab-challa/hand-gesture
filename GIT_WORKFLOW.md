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
# After editing main.py
git add main.py
git commit -m "Fixed drawing functionality"
git push
```

### Useful Commands:

**See what files changed:**
```bash
git status
```

**See detailed changes:**
```bash
git diff
```

**See commit history:**
```bash
git log
```

**Pull latest changes from GitHub (if working on multiple machines):**
```bash
git pull
```
