# Appendix A. Glossary

[← Previous](20-team-process.md) · [Contents](README.md) · [Next →](22-timeline.md)

Terms are listed alphabetically. The chapter where each term is discussed is given in parentheses.

**ACP (Agent Client Protocol)** — the protocol between an agent and an editor: sessions, the stream of messages, tool calls, confirmations. Junie implements it and adds its own extensions (Ch. 17).

**Agent token** — a credential by which the server recognizes a specific agent. Stored as a hash (Ch. 19).

**Alias (model alias)** — a stable short name (`gpt`, `opus`) that leads to a concrete model. It makes it possible to change the model without changing the user's configuration (Ch. 16).

**Artifact** — an intermediate result of the agent's work, with an explicit type and identifier. The foundation of the generation pipeline (Ch. 1).

**Allowlist of dependencies** — the list of packages the agent is allowed to install (Ch. 4).

**Budget (token budget)** — a limit on the size of the history that the agent maintains, estimating tokens from characters and calibrating the estimate against the provider's answers (Ch. 14).

**Worker** — a small stage of the pipeline with its own prompt, response format, and artifact (Ch. 1).

**Eco mode** — planning with the selected model and implementation with a cheaper model (Ch. 16).

**Effort (effort level)** — the degree of the model's reasoning before it answers. The set of levels depends on the model (Ch. 16).

**EmbArk** — indexing and search over code, with parsers for several languages (Ch. 14).

**Evals** — assessment of the agent's quality on a set of tasks. An expensive level of verification (Ch. 10).

**ExecutionContext** — a node of the agent's call tree: its parent, its request, its statistics (Ch. 7).

**FileChange** — an object describing a change to a file, with the content "before" and "after". The foundation of diffs and rollbacks (Ch. 8).

**Goal** — a long-lived state of a session that the agent holds between prompts (Ch. 18).

**HITL (human in the loop)** — confirmation of actions by the user, with the modes `AllowAll`, `AskAll`, and `Interactive` (Ch. 8).

**HistoryProcessor** — a strategy for shortening the agent's step history (Ch. 2, Ch. 14).

**JUNIE_HOME** — the directory of Junie's user data: logs, settings, sessions, cache (Ch. 11, Ch. 12).

**Junie Live** — a service in which the agent runs as a long-lived process with an event log and commands (Ch. 19).

**Junie Mix** — a ready-made profile with the levels `lite`, `normal`, `hard`, `frontier` (Ch. 16).

**Kineto** — the generator line, removed from HEAD in November 2025 (Ch. 4, Ch. 5).

**MCP (Model Context Protocol)** — the protocol through which external servers announce their tools to the agent (Ch. 13).

**Native launcher** — a program written in Rust that starts the JVM in its own process, preserving the process name and signal behavior (Ch. 12).

**Sandbox** — a constraint on the agent's commands through `srt`: which directories may be written and read (Ch. 15).

**Capability rule** — ACP extensions are enabled by a capability the client has declared, not by the client's identity (Ch. 17).

**RootExecutionContext** — the owner of a task's resources. It closes them once, in registration order (Ch. 7).

**RPC schema** — a description of a service in a dedicated DSL, from which the IDE's client and server are generated (Ch. 13).

**Recipe** — a verified instruction with a description, dependencies, and code fragments. It is chosen by the model from an index and checked by code (Ch. 4).

**Snapshot** — an archive of the agent's runtime state, stored outside the server (Ch. 19).

**Steerable command** — a command that can be executed while the agent is working (Ch. 18).

**Steering** — a user's message sent during the agent's work. Its outcome is `injected` or `startedNewTurn`, not an error (Ch. 18).

**Subagent** — a nested agent loop with its own conversation, which returns one result (Ch. 9).

**SWE-agent** — the approach that Matterhorn reproduced in 2024 for its action loop (Ch. 2).

**TeamCity logger** — the output of TeamCity service messages with a flow identifier, for parallel runs (Ch. 3).

**Capability filter** — the selection of a subset of MCP servers for a task. A filtered-out server can be enabled with the `enable_mcp` tool (Ch. 13).

**Worktree** — a separate git copy of the working directory, in which a subagent works in isolation (Ch. 9).
