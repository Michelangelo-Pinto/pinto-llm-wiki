# Prompt for New Conversations

Paste this at the start of a new conversation to resume work on v3 completion.

---

You are continuing work on the wiki-js-mcp v3 completion plan.

**First action:** Read `plans/v3-completion/index.md` to understand the current state.

Then:

1. Identify the first task with `status: pending` that has no blocked dependencies (check the "Depends On" column — all dependencies must be `completed`).

2. Read that task's MD file in `plans/v3-completion/tasks/` — it contains the objective, background, implementation plan, and completion criteria.

3. Execute the task. Follow the implementation plan in the task file.

4. When the task is done, update ALL of these files:
   - The task's own MD file: set `Status` to `completed`, fill in `Decisions` and `Notes`
   - `plans/v3-completion/roadmap.md`: update status table, add change log entry, update progress
   - `plans/v3-completion/decisions.md`: add any design decisions made
   - `plans/v3-completion/tasks/08-docs-updates.md`: update docs update checklist
   - Relevant files in `doc_v3/`: as specified in the task's "Documentation Updates" section
   - `plans/v3-completion/index.md`: update the status table and "Next Unblocked Task"

5. Repeat until all tasks are `completed`.

**Critical rules:**
- Read from filesystem, not memory. Every file encodes current state.
- Use subagents via the Task tool for independent tasks when possible.
- Never edit the plan file (`plans/v3-completion-plan-folder_*.plan.md`).
- Update documentation (`doc_v3/`) at every step — do not defer doc updates.
