# Chapter 9. Subagents: Working with Several Hands

An agent with a long history sooner or later runs into two problems: its context fills up, and its tasks start interfering with one another. Exploring the code, editing files, and checking the result in one conversation drags along everything that came before. The obvious way out is to launch nested agents: subagents. The main agent hands over a task, the subagent works in its own conversation, and it returns a result.

That sounds simple. The difficulty lies in **what exactly is passed between the agents**, how the results come back, and how to keep two agents from damaging the same files. This chapter draws on the document `docs/subagents.md` and on the history of how the mechanism appeared.

## 9.1. A subagent is a second loop

A subagent is the same loop as in Chapter 2, started from a tool of the main agent. The key difference: it has its own conversation. It **never sees the history of the main agent**. It receives the text of the task, a copy of the settings, and the shared environment: the MCP servers, the project context, the working folder. When the subagent finishes, it returns one final text.

Subagents do not talk to each other. The only things they share are the files on disk and a few process-level services. This is a rule from the document: "Subagents never talk to each other".

Separating the conversation is not a side effect but the central idea. Without it, the subagent would inherit all the noise of the main agent and lose its purpose: instead of isolation, there would be one large conversation with branches.

## 9.2. What is passed and what is not

The document compares the handover to hiring a contractor: you give them a work order, not your notebook. The table in the document shows exactly what goes in:

- **The task text** (`task`), plus the additional context that the main agent appends at the end.
- **Settings**: a copy of the parent's parameters with overrides: the model or its tier, the step budget, a ban on asking the user questions, the nesting depth.
- **Mode**: `CODE` (may edit files), `EXPLORE` (read-only), or `OTHER`. The main agent sets the mode, and the subagent receives it as a constraint.
- **The working folder and environment variables** of the parent.
- **The shared environment**, through a child execution context (Chapter 7): a lookup of a resource in the child context falls through to the parent.

What the subagent does **not** receive:
- the conversation history of the main agent;
- the user's system prompt;
- the plan of the main agent.

This has an important consequence. The description of the `spawn_subagent` tool states plainly that the plan must be put into the text of the task, because the plan itself is not available to the subagent. If the main agent does not do this, the subagent works without it. Passing context is the responsibility of the calling agent, not something automatic.

One more detail: the capability filter (which tools are available) is run again for the subagent, based on *its* task. The subagent does not blindly inherit the main agent's set of tools.

## 9.3. Four tools of the calling agent

The main agent manages subagents through tools:

| Tool | What it does |
|---|---|
| `spawn_subagent` | Starts a new run and returns an identifier such as `agent-1`. With an identifier, it continues a finished run or redirects a running one |
| `wait_for_subagent` | Blocks the caller until the specified runs finish |
| `stop_subagent` | Cancels the run's coroutine |
| `ask_agent` | Asks a running subagent a question without interrupting it |

Redirection (`steering`) works in a non-obvious way: if you pass the identifier of a running subagent, it stops and restarts with the new instruction added to the previous one. This is simpler than inventing a protocol for delivering a message into a running loop, but it is costly: the current step is lost.

`ask_agent` solves a different problem. A question to a running subagent must not stop it. So for the answer a separate **fork** is created: a copy of the target agent's state and history, which works read-only, is limited to three steps, and returns its answer only to the caller. The fork is the only place where history is passed between agents. The tool appeared in July 2026.

## 9.4. Blocking and background modes

A result can be obtained in two ways:

- **Blocking.** The `spawn_subagent` call waits for completion, and the subagent's output becomes the result of the tool. The main agent does nothing while the subagent works.
- **Background.** The run proceeds in parallel and, on completion, puts its result into a channel. Before its next step, the main agent drains the channel, and the results are inserted into the conversation as a `<subagents_status>` message with one block per run.

The background mode is what makes subagents useful. The main agent can start three investigations in parallel, continue its own work, and collect the results when they are ready. The format of `<subagents_status>` matters: the model clearly sees which run finished, with what status, and with what output. Without structure, it confuses the results of different subagents.

## 9.5. Edits: one merged result

A subagent that edits files records its edits in its own edit history (Chapter 8). When it finishes, its edits are **merged into the main agent's history as one composite edit**. For the user and for the `/revert` command, that is a single action, not a dozen small ones.

This decision explains why the edit history as an object matters. Without it, merging a subagent's edits into the parent's edits would be impossible: you need "before" and "after" for every file.

But a shared working directory has a limit. Subagents that do not work in their own copy write to the same files. That is why the main agent's prompt requires an "exclusive scope" for each call: one subagent edits one set of files, another edits different ones. This is a discipline, not a technical guarantee. The hard guarantee is an isolated working copy.

## 9.6. Isolating the working copy: worktrees

The argument `useWorktree` runs the subagent in its own git copy (a worktree). It appeared at the end of July 2026, together with a pool of worktrees for the subagents of the chat agent. The copy provides full isolation of edits: two subagents physically cannot damage each other's files. The price is merging the results back into the main branch, which becomes a separate task.

Choosing between "a shared folder with a discipline of scopes" and "a separate copy" is a typical trade-off. The shared folder is cheaper and simpler, but it requires the agents not to overlap in scope. A separate copy is more reliable, but it requires a merge. For read-only tasks the question does not arise: `EXPLORE` subagents do not write, so isolation is not needed.

## 9.7. Nesting

By default a subagent cannot launch subagents of its own: the nesting depth is zero. If nesting is allowed, the nested agent creates its own `DefaultSubagents` with its own list of runs, but reuses the parent's identifier counter so that identifiers do not collide. A marker inside the subagent prevents it from receiving the main agent's notifications.

Limiting nesting matters for two reasons. First, cost grows faster than the number of agents: each level adds its own model calls. Second, an error at one level is hard to diagnose when there are many levels. Nesting appeared in July 2026 as a separate option, and it is disabled by default.

## 9.8. Control from the interface

The user can open a running subagent, see its conversation, and send it a message. The message does not go through the main agent. The calling agent attaches an object, `CallerSubagentControl`, to the task, which puts incoming messages into a queue for each subagent. At a step boundary the subagent receives the message as an `<issue_update>` and continues its work without restarting. If the run has already finished, the message becomes the task of a new run.

An important detail: waiting for a result is not disturbed by sending a message. A calling agent that is waiting in `wait_for_subagent` keeps waiting for the real result. A user's message creates neither a false "stopped" status nor an early wake-up. This subtle rule is easy to break if user messages and subagent results travel through the same channel.

The mechanism appeared in November 2026, together with a subagent view in the interface.

## 9.9. The chat orchestrator: a separate process

The long-lived chat session has its own implementation. There each subagent runs as a **separate CLI process**, not as a coroutine in the same process. The refactoring that introduced this separation appeared in October 2026 (`JunieHarness`, `ChatSpawnSubagentTool`).

A child in a separate process receives even less context: the task text and the project directory, the model, the effort level and the step limit, and, for typed agents, the tools that the parent provides. The result comes back as a completion message in the chat's inbox.

Here the isolation boundary is stricter: a crash of the subagent cannot affect the parent process. The price is the overhead of starting a process and serializing everything that is passed. For long tasks this is a reasonable exchange.

## 9.10. History: from edits to subagents

The word "subagent" is older than the mechanism. In 2024 Matterhorn used a "sub-agent" for editing files: in August 2024 the tool `search_replace` appeared as part of a subagent editor (Chapter 8). It was an auxiliary model call for a single edit, not an agent with a loop.

Real parallel and background subagents for the main CLI agent appeared on 4 June 2026. Then followed:
- **8 June 2026** — the edit history moved from the context into the state of the main agent (the commit message: "move editsHistory from context to mainAgent state"). Merging a subagent's edits into the parent's history relies on this.
- **7 July 2026** — nesting (`childSubagentDepth`).
- **15 July 2026** — `ask_agent` with a fork.
- **28 July 2026** — a pool of worktrees for subagents.
- **19 October 2026** — the refactoring of the chat orchestrator with separate processes.
- **4 November 2026** — control of a subagent from the interface.

The mechanism grew from the simple (a blocking call) to the complex (background runs, nesting, forks, isolation, control) within five months. The order is sensible: first the result has to come back at all, and only then can several agents work at the same time.

## 9.11. What follows

1. **Conversation isolation is the foundation.** A subagent without the main agent's history works more cleanly, but it requires the calling agent to pass the needed context explicitly.
2. **The result is structured.** A status block with the identifier and the output protects against confusion.
3. **Edits are merged in one action**, and for that the edit history must be an object.
4. **Shared files require discipline**, and for parallel work it is better to isolate the working copy.
5. **Nesting is off by default**: it is expensive and hard to debug.
6. **A question must not stop the work.** For questions you need a fork, not a restart.
7. **A user's message and an agent's result are different channels.** Waiting for a result must not be interrupted.

## Exercises

1. Implement a subagent as a coroutine with its own conversation. The main agent should pass it only the task text. Check that the subagent does not know details the parent knows, unless they are included in the task.
2. Add a background mode: `spawn` returns an identifier immediately, and the result arrives in a channel. Before each step, the main agent drains the channel and inserts a status block. Verify the order and the contents of the blocks with three parallel subagents.
3. Implement merging the edits of two subagents into one composite edit. Verify that a single rollback restores the files to their original state.
4. Create two subagents that write to the same file. Show that without exclusive scopes the edits conflict. Then give each subagent its own scope and verify that there is no conflict.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The mechanisms and files were checked against HEAD. The structure of the description relies on `docs/subagents.md`, which is the primary source itself; quotations from it are paraphrased.
