# Appendix B. Timeline

The dates are dates of commits on the `main` branch of `junie-repo`, or dates when a concept appeared in the history, as indicated in the chapter. The history was taken as of 18 November 2026. Commits on other branches were not considered. Chapters where each event is discussed are given in parentheses.

## 2024

- **March** — the first Matterhorn commits; HumanEval experiments (22 March) (Ch. 3).
- **April** — retries of HTTP requests (3 April) and cancellation through "Stop" (2 April) (Ch. 5). Parallel task runs (16 April) (Ch. 3). The SWE-style agent loop (17 April) (Ch. 2). The recipe catalog (18 April) (Ch. 4). The allowlist of npm dependencies (18 April) (Ch. 4).
- **May** — the action format adapted for GPT-4o (15 May) (Ch. 2). The cost limit for generation (23 May) (Ch. 5).
- **June** — reproduction of SWE-agent's behavior: the bash interface (10 June), the 40-step limit (18 June) (Ch. 2). A timeout for bash commands (27 June) (Ch. 5).
- **July** — the code is imported (11 July) (Ch. 7). History settings for agents (12 July) (Ch. 14).
- **August** — the `search_replace` subagent editor (16 August) (Ch. 8, Ch. 9). The Redis cache of model requests (27 August) (Ch. 10). A retry of generation when tests fail (29 August) (Ch. 1).
- **September** — the split into modules core, ej-core, ej-ui, ej-idea, ej-pycharm, webgen (13 September) (Ch. 6). The agent's context in `userData` (17 September) (Ch. 7).
- **October** — a single place for the cache and a log of misses (14 October) (Ch. 10). Closing the context against a leak (28 October) (Ch. 7). Retries for Anthropic (12 October) and for rate limits (31 October) (Ch. 5).
- **November** — the plugin renamed (12 November) (Ch. 11). File snapshots before and after an edit (22 November) (Ch. 5). The first mention of sandbox in the history (24 November) (Ch. 15).
- **December** — the logs renamed to "Collect Junie Logs" instead of Matterhorn (5 December) (Ch. 11). Kineto (9 December) (Ch. 5). Cancelling an artifact in favor of another (10 December) (Ch. 5).

## 2025

- **February** — handling of the error "context exceeded" (17 February) (Ch. 14). Release tags v0.31.x (19 February — 7 March).
- **March** — components renamed because of the conflict with AI Assistant (10 March) (Ch. 6, Ch. 11).
- **April** — feature flags (1 April) (Ch. 6). The brave mode and the allowlist of actions (25 April) (Ch. 8).
- **May** — the MCP integration (20 May) (Ch. 13). The first `apply_patch` for the frontend (27 May) (Ch. 8).
- **June** — support for the ingrazzio token in Junie Runner (17 June) (Ch. 11, Ch. 16).
- **July** — Junie CLI (15 July) (Ch. 12). The standalone module (16 July) (Ch. 12).
- **August** — EmbArk indexing and search (28 August) (Ch. 14). Error checks moved into services (11 August) (Ch. 8). The refactoring of the context toward narrow interfaces (29 August) (Ch. 7).
- **October** — the ACP and the `--acp` flag (7 October) (Ch. 17). `UnlimitedStepsHistoryProcessor` (2 October) (Ch. 14). The `cli-evals` module (24 October) (Ch. 10). The `JUNIE_HOME` directory (15 October) (Ch. 11, Ch. 12). The monorepo (29 October) (Ch. 6).
- **December** — models of the Grok family (6 December) (Ch. 16). OAuth for MCP (6 December) (Ch. 13). The move of the OAuth code to another module (12 December) (Ch. 13).

## November 2025: removal of Kineto

- **28 November** — "Remove Kineto": 1,577 files and 151,412 lines removed. The webgen generator and the recipe catalog went with them (Ch. 4, Ch. 5).

## 2026

- **January** — IDE MCP tools in `ide-server` (9 January) (Ch. 13). Support for the Windows terminal (22 January) (Ch. 12).
- **February** — CI instructions in the README with the mandatory checks (3 February) (Ch. 10, Ch. 20). Skills in `.junie/skills` (6 February) (Ch. 20). `enable_mcp` (6 February) (Ch. 13). The capability filter, `CapabilityFilterExecutor` (11 February) (Ch. 13). The cache key built from the final text of the request (11 February) (Ch. 10). Model aliases (26 February) (Ch. 16). Reactive availability of models in ACP (26 February) (Ch. 17).
- **March** — structured output of MCP and collapsing of long results (2 March) (Ch. 13). The E2E module and the Snapshotter (18 March) (Ch. 10).
- **April** — effort levels, `EffortLevel` (16 April) (Ch. 16). The specification of token and cost accounting (29 April) (Ch. 16). The first mentions of "goal" in the history (24 April) (Ch. 18).
- **June** — parallel and background subagents for the CLI (4 June) (Ch. 9). The edit history moved into the state of the main agent (8 June) (Ch. 9). Categories of models and effort in ACP (15 June) (Ch. 17). The rename of Junie Live (18 June) (Ch. 19). The commands API of Junie Live (30 June) (Ch. 19).
- **July** — nesting of subagents (7 July) (Ch. 9). `ask_agent` with a fork (15 July) (Ch. 9). Steering in ACP (21 July) (Ch. 18). Worktrees for subagents (28 July) (Ch. 9).
- **August** — semantic search in the CLI (4 August) (Ch. 14). ACP v2: message identifiers (4 August) (Ch. 17). The data-model document of Junie Live (31 August) (Ch. 19). The document on the goal extension (20 August) (Ch. 18).
- **September** — the session-replay contract in ACP v2 (2 September) (Ch. 17). Agent tokens in Junie Live (7 September) (Ch. 19). The opt-in sandbox (16 September) (Ch. 15). Sandbox support for Linux (25 September) (Ch. 15). The lifecycle document for the execution root (23 September) (Ch. 7). The economy-mode toggle (29 September) (Ch. 16).
- **October** — the error code `steering_turn_busy` in ACP v2 (1 October) (Ch. 18). `ProcessRestart` (8 October) (Ch. 12). Sequential execution of tools for xAI and Gemini models (13 October) (Ch. 8, Ch. 16). The chat orchestrator with separate processes (19 October) (Ch. 9). Narrowing of the MCP authorization methods (October) (Ch. 13).
- **November** — parallel edits run one at a time (2 November) (Ch. 8). The class `SteerableAcpCommand` (2 November) (Ch. 18). `/teleport` (3 November) (Ch. 12). The native launcher for macOS arm64 (4 November) (Ch. 12). Retry of a step on overflow and calibration of the token estimate (4 November) (Ch. 14). The team rules and skills in `AGENTS.md` and `.agents/skills` (9 November) (Ch. 20). The publication of the model catalog for ACP (18 November) (Ch. 16).

## What the dates mean

- The first appearance of a string or class in the history does not always coincide with the moment the mechanism started to work. For example, `CapabilityFilterExecutor` first appears on 11 February 2026, but its behavior may have taken shape earlier.
- For some mechanisms, the first appearance is reconstructed only from a string or a class name. This is indicated in the relevant chapters.
- The date "November 2025" for the removal of Kineto is the date of a commit. It should not be confused with the date when the idea was abandoned: the generator line ended gradually.
