# Mandatory GitLab workflow

For every development task in this repository:

1. Verify that the preceding task's MR was actually merged, not merely approved.
   Do not begin the next implementation while its predecessor awaits merge.
2. Inspect status, preserve unrelated work, and fetch origin. Safely update local
   main from origin/main (fast-forward only), then create a fresh feature branch.
   Never implement directly on main or reuse an old task branch.
3. Keep changes scoped to the task, run relevant checks, and stage only related
   files. Create meaningful commits, push, and open an MR targeting main.
4. Describe purpose, changes, verification, important limits/risks, reproduction
   where relevant, and exclusions in concise English for human reviewers. Link
   relevant issues when available. Distinguish synthetic from real-data evidence.
5. Report the MR URL, branch, commits, and test outcomes. Stop for explicit user
   approval. Never merge an MR without explicit approval.

Never force-push, hard-reset, discard work, or overwrite teammates' changes.
Do not commit raw/private recordings, datasets, credentials, secrets, large
generated artifacts, or temporary outputs. Keep experiment artifacts organized
under their experiment directory; preserve teammates' Data and AI pipelines.
