A file-based personal planning system operated through an AI agent.

The user interacts with the agent using natural language. The agent manages the planning data through a deterministic CLI.

## Structure

```text
.
├── AGENTS.md
├── goals.json
├── history
│   ├── goals.done.json
│   ├── projects.done.json
│   └── tasks.done.json
├── plan.json
├── plan.py
├── profile.md
├── projects.json
├── schema
│   ├── daily-history.schema.json
│   ├── goal.schema.json
│   ├── plan.schema.json
│   ├── project.schema.json
│   ├── state.schema.json
│   └── task.schema.json
├── state.json
└── tasks.json
```

### Core concepts

* **Goal** — an important long-term outcome.
* **Project** — a finite body of work that produces a specific result and contributes to one or more goals.
* **Task** — a concrete, actionable piece of work.
* **Plan** — the work selected for the current day.
* **State** — a small snapshot of the current situation.
* **History** — records of completed work and past daily activity.

## Using the Agent

The user should interact with the agent through natural language.

Examples:

```text
Plan my day.
```

```text
Add a task to write the integration tests.
```

## Missing Information

When required information is missing, the agent should ask the user rather than inventing it.

Optional information does not need to be requested unless it is useful for the current planning decision.

## Daily Workflow

```text
User provides context
        ↓
Agent reviews current state
        ↓
Agent creates or updates the daily plan
        ↓
User reports what happened
        ↓
Agent records the actual results
        ↓
History is preserved for future planning
```

The daily plan represents **intended work**.

Daily history represents **what actually happened**.

## Important Files

`AGENTS.md` contains the agent's operating rules.

`profile.md` contains persistent user preferences and planning context.

`goals.json`, `projects.json`, and `tasks.json` contain active planning data.

`plan.json` contains the current daily plan.

`state.json` contains the current planning snapshot.

`history/` contains historical records.

`schema/` contains JSON schemas used for validation.

