# Junie: How to Build an AI Agent

A book about building an AI coding agent, based on the real history of the Junie repository (Matterhorn → Junie). Each chapter describes a problem the team faced, what they tried, what survived, and what it teaches. Commit titles and dates are cited; commit hashes and author names are not.

Status: draft. The chapters were translated from the Russian edition and are also unproofread.

## Contents

Part I. The Matterhorn prototype (2024)

1. [From PRD to Application](01-from-prd-to-app.md) — the generation pipeline, workers, and artifacts.
2. [The Agent Loop](02-agent-loop.md) — actions, observations, the response format, and SWE-agent.
3. [Parallelism and Benchmarks](03-parallel-and-benchmarks.md) — HumanEval, parallel tasks, and TeamCity logs.
4. [Recipes: Knowledge the Agent Should Not Invent](04-recipes-knowledge.md) — the catalog and the dependency allowlist.
5. [Reliability](05-reliability.md) — retries, cancellation, timeouts, the budget, and state snapshots.

Part II. The IDE agent (2024–2025)

6. [Modules: From Six to Twenty](06-modules.md) — the split into core and ej-core, the dependency-direction rule, and the fate of the IDE line.
7. [The Execution Context](07-execution-context.md) — the root and the nodes of the tree, resource ownership, closing, and races.
8. [Tools and Edits](08-tools-and-edits.md) — the action contract, three generations of edits, confirmations, and command classification.
9. [Subagents](09-subagents.md) — conversation isolation, background mode, merging edits, nesting, and control.
10. [Testing a Non-Deterministic Agent](10-testing-nondeterministic.md) — the request cache, miss checks in CI, E2E tests, and evals.
11. [Names: Renaming Without Breaking Users](11-naming-and-rename.md) — layers of names, environment variables, and serialization.

Part III. From the IDE to the terminal (2025–2026)

12. [From the IDE to the Terminal: Standalone and CLI](12-standalone-cli.md) — the modes of one binary, session transfer, restart through a file, and the native launcher.
13. [Tools From Outside: MCP and the IDE](13-mcp-and-ide.md) — the MCP client, the capability filter and `enable_mcp`, and the RPC schema of the IDE.
14. [Context Management](14-context-management.md) — the token budget, calibration, history compression, the agent's memory, and code search.
15. [The Sandbox](15-sandbox.md) — process constraints, protection of the policy file, delivery of `srt`, and the boundaries.
16. [Many Models](16-multi-model.md) — aliases, effort levels, the economy mode, the public model catalog, and cost.

Part IV. Protocols, services, and the team (2025–2026)

17. [ACP: The Protocol Between the Agent and the Editor](17-acp.md) — protocol versions, capability-gated extensions, and an honest list of debts.
18. [Steering a Running Agent: Steering and Goals](18-steering-and-goals.md) — messages during a turn, command classes, and a goal as session state.
19. [Junie Live: The Agent as a Service](19-junie-live.md) — the data model, the event log, snapshots through signed links, commands, and gaps. The server-side code is not in this repository.
20. [How a Team and Agents Ship Code Together](20-team-process.md) — AGENTS.md, skills, PR rules, agent review, and CI checks.

Appendices

21. [Glossary](21-glossary.md)
22. [Timeline](22-timeline.md)

## Notes for readers

- Commit titles are quoted as they appear in the history. Where a commit message gives no reason, the chapter says so.
- Chapters 4 and 5 describe code that was removed from HEAD in November 2025 (the Kineto line). Each such chapter has a section on what became of it.
- Chapter 19 describes a server that is not in this repository. Its conclusions come from the design document.
- The history does not contain accuracy metrics for the early experiments, so the book gives no solve rates.
