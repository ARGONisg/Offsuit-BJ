# Git Commit and Remote Conventions

1. **Commit Message Discipline**:
   - Do NOT include internal roadmap, stage, or task labels such as "Phase 1:", "Phase 2:", "Step 1:", etc.
   - Use clear, imperative, and descriptive commit titles that describe the actual technical change (e.g., "Add persistent session logging to desktop bot").

2. **Rewording & Remote Pushes**:
   - If commits need to be reworded or amended after pushing to a remote branch, always use `git push --force-with-lease origin <branch>` to safely verify the remote reference before overwriting.
