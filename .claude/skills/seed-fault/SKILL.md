---
name: seed-fault
description: Break the pipeline on purpose, record the red test output and hook stderr, then restore it. Use when asked to seed, inject, or test a fault, or to check whether the test suite catches a specific bug.
allowed-tools: Read, Edit, Bash(python -m pytest*), Bash(make*), Bash(git diff*), Bash(git status), Bash(git commit*), Bash(git checkout -- src/*), Bash(git checkout -- tests/*)
---

# Current state

!`git status --short; git log --oneline -1`

# Seeding a fault: $ARGUMENTS

Work in this order. Do not fix anything before step 4 is written down.

1. **Start green.** Run `make test`. If anything fails, stop and say so:
   a fault seeded on a red suite proves nothing.

2. **Make the smallest change that produces the fault** described in
   $ARGUMENTS, with the Edit tool so the PostToolUse hook sees it. One file,
   as few lines as possible. Never touch `data/raw/` with Edit or Write.
   If the fault is a Bash-side change to raw data, use a copy outside the
   repo and say the hook cannot see it.

3. **Record, do not describe.** Paste, verbatim:
   - `git diff` of the change
   - the hook's stderr and whether it exited 2 (or that it stayed silent)
   - `make test` output: the FAILED lines and the summary line
   Commit the broken state: `Seed fault: <one line>`.

4. **If the suite stayed green, that is the finding.** Say which test
   should have caught it and why it did not. Write the missing test in
   `tests/test_leakage.py` (so the hook runs it) and show it going red
   against the still-broken code before restoring anything.

5. **Restore** with the smallest edit, rerun `make test`, and paste the
   green summary line. Commit: `Fix fault: <one line> (<n> turns)`, where
   n counts edit-and-verify cycles after the first red output.

6. **Append a section to `docs/SEEDED_FAULTS.md`** with the blocks from
   step 3, the turn count, and the fix. Real output only. Never paraphrase
   a failure message.

Do not change `FORBIDDEN`, the split dates, or `reports/metrics.json` while
a fault is seeded. Never run `make train` on a broken tree.
