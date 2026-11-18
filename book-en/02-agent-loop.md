# Chapter 2. The Agent Loop

[← Previous](01-from-prd-to-app.md) · [Contents](README.md) · [Next →](03-parallel-and-benchmarks.md)

Chapter 1 had a pipeline: stages run one after another, and each produces an artifact. This chapter is about something different: a loop in which the model itself decides which action to take next, sees the result, and carries on. That is what an agent is in the narrow sense.

The difference between a pipeline and an agent is fundamental. In a pipeline the order of steps is known in advance. In an agent the model chooses the next step as the work proceeds, and it must be able to stop.

In the history of Matterhorn this transition took about three months: from 17 April to the end of June 2024.

## 2.1. The minimal loop

Any agent reduces to four things:

1. The model receives the state: the task, the history, the current contents of the project.
2. The model returns an action in a fixed format.
3. The action is executed, and its result (the observation) is added to the history.
4. The loop repeats until the model calls a finish action or the budget runs out.

In the commit `SWE Agent initial commit` (17 April 2024) this scheme appeared in code. The commit added the files `AgentActions.kt`, `IssueAgentWorker.kt`, `IssueSingleStepAgentWorker.kt`, and `ResolveIssueAgentAction.kt`: 338 added lines in total.

The set of actions in the first version was deliberately small:

```kotlin
fun getAvailableActions(context: ExecutionContext): List<AgentAction> {
  return listOf(
    ShowProjectStructureAgentAction(),  // get_current_project_structure
    EditFileAgentAction(),              // edit_file
    CheckCompilationAgentAction(),      // compilation check
    FinishAgentAction()                 // finish
  )
}
```

Four actions are the agent's entire world. Everything else is done through them. This rule still holds today: the fewer actions there are, the easier it is for the model to pick the right one.

Each action has three parts: a name, a description for the model, and two functions: `review` (check the request before execution) and `execute` (run it). The check before execution appeared immediately: the model could request a nonexistent action or pass wrong arguments, and this had to be caught before anything changed on disk.

## 2.2. The observation: the result of an action that the model sees

The commit `Add observation to the IssueActionPlanWorker` (17 April 2024) is small, three lines. But it matters: without an observation the model does not know what happened. It writes `edit_file` and does not see whether the file was created, whether it compiles, or whether the line to replace was found.

From this point on, every step contains two messages: the model's action and the environment's observation. The history grows, and after a few steps the context overflows. The commit `reproduce swe-agent: add shortening of old user messages` (18 June 2024) introduced shortening: old user messages (including observations) are collapsed, while the most recent ones stay in full.

Later this was formalized as `Last5ObservationsHistoryProcessor`. Its constant `MAX_FULL_USER_MSGS = 5` keeps the five most recent user messages in full, collapses the rest, and gives the model a short notice about how many messages were collapsed. This is an early example of what later became history compaction (see Chapter 14). Note that the limit is counted in messages, not tokens. It is a simple decision, and it is also its main weakness.

## 2.3. The response format: where agents break most often

If I had to name one reason agents fail, I would name the response format. The model produces text, while the code expects a structure. A mismatch, and the loop stops.

In the history of Matterhorn this showed very clearly. The early format described actions in free text:

```
Can't parse an action description:
```

The error occurred when the model added reasoning, code blocks, or stray separators. The commit of 15 May 2024 rewrote the instruction. Its key changes:

- Instead of a free-form description, an explicit `ACTIONS:` block with `------` separators.
- Each action is described by three fields: `ACTION`, `ARGUMENTS`, `DESCRIPTION`.
- An explicit rule: "If this is not an action, but just text/reasoning/code, then remove it from the answer".
- An example of a correct answer right in the prompt.

The commit message names the cause directly: problems with GPT-4o. The model had changed, and a format that worked on one version broke on another. The general lesson: **the response format is part of the contract with the model, and it must be tested on every model change**.

A second wave of format changes came through SWE-agent. The commit `change action format (make similar to swe-agent), add demo` (17 June 2024) moved the format closer to the original SWE-agent: the command and its arguments in a bash block. Later, on 29 August 2024, the parser was taught to read ```` ```bash ```` blocks, because models often wrapped commands in exactly those.

## 2.4. Reproducing SWE-agent

For Matterhorn the idea was not to reinvent the loop but to adopt a known approach. In June 2024 a series of commits with the prefix `reproduce swe-agent:` appeared. They show exactly what was carried over:

- `add shellInterface, add all commands` (10 June). A bash interface: the agent runs commands in a persistent session.
- `add exit code control for sigle-line bash commands` (17 June). The exit code of each command is returned to the agent.
- `fixes for multiline commands` (14 June). Multi-line commands are executed separately from single-line ones.
- `set 40 steps maximum (see figure 14, 15 from swe-agent paper)` (18 June). The step limit is taken from the SWE-agent paper: its graphs show how quality grows and where it plateaus.

The step limit is a good example of how a general research result becomes a constant in code. The value 40 was not derived from Matterhorn's task; it was taken from the paper and checked on the team's own data only partially (the history contains no metrics).

A note: the history contains no tables comparing results. One cannot claim that "40 steps is optimal for Matterhorn". One can only say that this is what was decided.

## 2.5. Editing tools

The hardest part of an agent is editing files. The model can write a file in full, replace a fragment, or insert lines. Each way has its own failure modes.

In August 2024 a series of commits about editing approaches appeared:

- `add ReplaceLinesWorker` (20 August 2024). Replacement by line numbers.
- `fix bug with wrong syntax error in SearchReplaceWorker` (19 August 2024). Replacement by a fragment: the model must reproduce the original text exactly.
- `drop redundant response types, put edit workers into separate package` (22 August 2024).
- `Refactoring of EditWorkers` (6 and 9 September 2024).

Editing by line numbers breaks quickly if the model is off by one. Editing by fragment breaks if the model changes whitespace. The resulting design: several specialized workers (`SearchReplaceWorker`, `RewriteFileWorker`), each with its own format, and a separate step that checks the result.

This step is **RankingCritique**. A commit dated 10 August 2024 added a worker type `RankingCritique`. It receives a list of proposed actions (`actionsToRank`) and returns a rank and a score for each. The response format is checked by the same mechanism as in Chapter 4, `UserReviewedRequest`: if the number of ranks does not match the number of actions, the model gets an error message and answers again. It costs more than a single call, but less than rolling back a wrong edit.

A commit of 18 September 2024 added the setting `EditWorkerCritique` through an environment variable. The critic was therefore optional: it could be switched on and off without rebuilding.

## 2.6. What works and what does not

By the end of June 2024 the agent had everything it needed to work: the loop, observations, history, a set of actions, and editing. But it remained fragile, and the main effort went not into new capabilities but into the robustness of the format and the tools.

A table of what mattered most:

| Problem | Solution in the history |
|---|---|
| The model does not produce the structure | An explicit format with an example |
| A long history overflows the context | The five most recent messages kept in full, the rest collapsed |
| An edit breaks the file | Several editing workers and a critic |
| The agent does not see the result | An observation after every action |
| The loop does not end | A step limit |

## 2.7. What became of it in the current code

The loop, the observations, and the actions survived the transitions. The class `IssueSingleStepAgentWorker`, created in the commit "SWE Agent initial commit", is still present in HEAD (in five files), and `ExecutionContext` and `ArtifactRequestExecutor` have become the foundation of the core. The history-shortening mechanism also survives, but with renames. In `ej-core/.../agent/history_processors/HistoryProcessors.kt` the value `Last5Observations` is still in the `HistoryProcessors` enumeration. The response class was renamed to `LastNObservationsResponse`, but its serialized name remained `Last5ObservationsResponse`: the agent can restore history from saved data by that name, so it cannot be changed without a migration.

Some specific decisions described here are no longer in HEAD and should be read as historical points. `RankingCritique`, `IssueActionPlan`, and the format with the `ACTIONS:` block do not appear in HEAD. The actions `edit_file`, `get_current_project_structure`, and `check_compilation` are also not found: the agent's toolset in the current version is different. If you want to reproduce the format from this chapter, rely on this book and the commits, not on the current code.

## Exercises

1. Implement a minimal agent loop with the four actions from Section 2.1 (read a file, write a file, run a command, finish). Use any model through an API. Log every action and observation.
2. Break the response format on purpose: ask the model to answer "in free form" and see how quickly the parser fails. Then add an explicit format with an example and check it on the same task.
3. Limit the history to the five most recent observations and compare how quality changes on a task of 15 steps.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates.
