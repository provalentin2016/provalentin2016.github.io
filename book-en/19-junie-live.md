# Chapter 19. Junie Live: The Agent as a Service

[← Previous](18-steering-and-goals.md) · [Contents](README.md) · [Next →](20-team-process.md)

Until now the agent has run on the user's machine: in the IDE, in a terminal, in an editor. Junie Live is an attempt to move it onto a server. The agent runs as a long-lived process, it is visible in a dashboard, a command can be sent to it, its state is kept between runs, and the whole team talks to it through Slack.

One important point must be stated at the outset, because this chapter cannot avoid it. **The server-side part of Junie Live is not in this repository.** `junie-repo` contains three things: a detailed document of the data model (`docs/junie-live-data-model.md`), the configuration of the agent that serves the Slack bot (`.junie-live/`), and the chat orchestrator (`ej-chat-core`). So this chapter relies on the design recorded in the document and on what is visible from the agent's side. Conclusions about the server itself come only from the document.

## 19.1. Three jobs of the service

The document begins with three goals:

1. **Observe the agent's runs.** The agent registers each run as a "running instance" inside a project and reports its life through an append-only stream of events. The dashboard builds from this a tree: projects, agents, instances, and a timeline of events.
2. **Persist state between runs.** The agent executes inside a sealed, ephemeral sandbox (Chapter 15) that is destroyed at every launch. So the state of the agent's runtime is packed into a single opaque zip and restored at the next launch.
3. **Drive a run with commands.** A user on the dashboard sends a typed, asynchronous command to a specific instance, for example "collect the sandbox logs". The agent polls the queue, executes the command, and commits exactly one result: success or failure.

Note that each of these jobs touches the same object but with different frequencies and different risks. Events are cheap and numerous. State snapshots are large and rare. Commands are small but need delivery guarantees. The data model has to account for all three.

## 19.2. A vocabulary: people, logins, agents

The first good idea of the document is the separation of people and logins. The record `app_user` is a **person** inside the system, unique by a normalized email address. The record `external_user` is a **concrete sign-in** through which that person can enter (currently one external source). Project access is granted to the person through `project_member`, not to the login.

Why does this matter? If permissions hung off the login, changing the way someone signs in would cut them off from their projects. With the separation, only the login binding changes, and the permissions stay.

The project roles are ordered: `VIEWER` is less than `DEVELOPER`, which is less than `OWNER`. A project without members can be "claimed" by the first person who signs in — an explicit rule for inherited projects, not an accidental hole.

The agent is also a first-class entity: unique by the pair "project + name", with its own instances and snapshots. The agent token (the prefix `jlagt_`, the so-called agent token) is stored only as a SHA-256 hash. This is standard practice for secrets, and the document records it explicitly rather than relying on the implementation to have done it by itself.

## 19.3. State is a log, not a column

The least obvious decision: a running instance has **no status column**. Its current state is the `event_type` of the most recent entry in the event log. The document calls this a "state-transition log", a log of transitions rather than a full event-sourcing model.

Why not a column? A status column is updated in place, and it is easy to let it drift from the real history. A log only appends, and the history stays intact. A new event type needs no schema migration, because `event_type` and `data` are open fields.

The cost of this decision is described in the section on gaps (below): the current state is determined by sorting on the creation time, and when two times coincide the result becomes non-deterministic. The flexibility of the log and the requirement of exact ordering pull in different directions, and the document acknowledges this.

## 19.4. Snapshots: the server does not hold the bytes

The agent's state snapshots are zip archives, which can be large. The document's decision: the server does **not** accept or store these bytes. It issues short-lived signed links through which the agent's worker uploads or downloads the archive **directly** to and from cloud storage. The database holds only a pointer to the object (`blob_cloud_storage_ref`) and the bookkeeping of the snapshots: which instance created it, when, and how to find and restore it.

The advantages are obvious: the server does not become a bottleneck for traffic, and it does not need to understand the content. But there is a cost too. If a signed link expires before the upload, the snapshot remains in a pending state, and it has to be cleaned up separately. The document mentions such cleanup for abandoned pending snapshots.

A lesson that appeared in Chapters 5 and 7: **the boundary of data ownership is the boundary of responsibility**. The server is responsible for metadata and ordering, but not for content.

## 19.5. Commands: one result per command

Commands are the most interesting part of the model. A command is a request that the agent takes from the queue and executes. The result is a separate record, `command_completion`, with a one-to-one constraint: `UNIQUE (command_id)`.

Why is the result a separate record rather than fields in the queue row? Because a command can have several competing outcomes. The agent may finish it with success or with an error. The user may cancel it. If a cancellation and a completion arrive at the same time, whoever writes first wins. The second write hits `ON CONFLICT DO NOTHING` and changes nothing.

This is a standard idempotency technique, and the document calls it an "idempotency seam": a repeated commit of the result is safe, because the unique constraint refuses a second write. Note that the logic for resolving the race is not in the application code but in the database schema. The schema protects against the error even where the application got it wrong.

Additionally, the command type (`command_type`) and its content (`payload`) are open. A new command type needs no migration, but it does require that a handler for the type exists. Openness is a gain for evolution and a risk for consistency, and the document describes both.

## 19.6. Gaps: an honest list

Section 9 of the document calls itself "Gaps and unenforced invariants". There are five items.

**G1. A storage reference is created before its owning row.** If the server crashes between the two writes, an object without a database record remains in storage. This is a typical problem of distributed writes without a shared transaction.

**G2. The core invariants live in application code, not in the schema.** Constraints that could be expressed in the database are checked in software. The program can be wrong; the database cannot.

**G3. Ordering depends on creation time without a tiebreaker.** If two events have the same time, their order is undefined, and the current state may differ when read again. Events have no sequence number, and at-least-once delivery allows duplicates without an idempotency key. The fix: add a monotonic tiebreaker (order by time and identifier) and a deduplication key.

**G4. Access rights exist, but coarser invariants still live in the code.**

**G5. A command taken into work can hang forever.** If the agent takes a command from the queue and never completes it, nothing returns it. There is no visibility timeout and no sweeper that would turn such commands into errors. The command stays incomplete until a user cancels it by hand.

Why is this list valuable for the book? Because it shows the difference between "it works" and "it is correct under failure". A system that works in normal operation can have all five gaps. The document records them as debts with proposed fixes, rather than hiding them.

For G5 the authors propose a server-side timeout and note that the contract with the agent would not change. This is an important detail: the fix does not require rewriting the client.

## 19.7. The Slack agent: what is visible from the agent's side

From the repository one can see the configuration of the agent that serves the Slack bot. The file `config-slack-bot.yaml` describes the profile `slack-bot` and several decisions, each a lesson about security.

- **Restricted branches.** The agent may push only to branches that match the pattern `slack-bot/*`. Everything else, including the main branch, is forbidden. A bot that could write to `main` is a threat, even if it does so correctly.
- **Commit identity.** Commits are signed with a separate identity of the agent, not with a developer's personal account. This matters for audit: the history shows what the bot did.
- **Connections without long-lived keys.** The document says that the GitHub App key and the installation identifier do not enter the workflow at all. Instead, the supervisor obtains short-lived project keys, scoped to a single repository, and refreshes them through a local mechanism.

The shared logic is visible here: **minimal rights, short lifetimes of secrets, and an explicit name for the agent**. The same principle as in the sandbox (Chapter 15) and in ACP (Chapter 17).

The configuration also contains a workaround for a quirk of `actions/checkout`: after cloning, the remote address is normalized, because otherwise `git fetch` would use a different route. Such a step is easy to miss, so it is recorded in the README next to the configuration.

## 19.8. The chat orchestrator

The overlap with Chapter 9: the main chat agent lives in `ej-chat-core`. It receives messages from chats (Slack too), decides whether to answer itself or to launch a subagent, and each subagent runs as a separate process. The tools `ChatSpawnSubagentTool`, `ChatAskAgentTool`, and `ChatStopSubagentTool` describe the control. Judging by its name, `ChatReplayRecorder` records the course of work for replay — an approach close to the request cache of Chapter 10.

The orchestrator is the thing closest to the Junie Live service from the agent's side. The rest is the document and the server implementation, which is not in the repository.

## 19.9. Chronology

- **18 June 2026** — the rename to "Junie Live agent".
- **30 June 2026** — the commands API on the server side.
- **31 August 2026** — the data model document (the commit "Junie Live domain model: concept-level doc, skill routing, data-model relocation").
- **7 September 2026** — agent authentication with a token alongside the project keys.

It is clear that over the summer of 2026 the service went from a name to a commands API and agent authentication. The data-model document appeared at the end of August, after the first APIs: it records decisions and gaps, not only a plan.

## 19.10. What follows

1. **Separate people from ways of signing in.** Tie permissions to the person.
2. **Store state as a log of transitions** when history matters more than the current value. But decide the ordering of events in advance.
3. **Do not route large data through the server** if the server does not need to understand it. Issue short-lived links.
4. **Make the result of a command a separate record with a unique constraint**: this protects against races without logic in the code.
5. **Record your gaps in the project.** A list of what is not guaranteed is more useful than a list of what works.
6. **Limit the bot's branches and rights.** Secrets are short-lived, and the agent is signed separately.
7. **Do not put a server where a client will do.** A service is justified when shared visibility and access from different devices are needed.

## Exercises

1. Design an event log for an agent instance. Define the event types and the ordering. Add a sequence number and verify that two events with the same time are ordered predictably.
2. Implement a command queue with a separate result record and a unique constraint on the command. Verify that when the agent's "success" and the user's "cancel" arrive at the same time, exactly one result is recorded.
3. Add a timeout for commands that were taken into work and not completed. When the timeout passes, the command becomes an error. Verify that the client receives a result rather than waiting forever.
4. Write a list of gaps for your own service: for each, name the failure that would trigger it and the fix needed. Separate the fixes that can be made without changing the client from those that require a change.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The data model is `docs/junie-live-data-model.md`; the list of gaps is section 9 of the same document. The agent configuration is `.junie-live/config-slack-bot.yaml` and its README. The server implementation is not in this repository, so conclusions about it are drawn only from the document.
