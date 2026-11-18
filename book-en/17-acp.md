# Chapter 17. ACP: The Protocol Between the Agent and the Editor

[← Previous](16-multi-model.md) · [Contents](README.md) · [Next →](18-steering-and-goals.md)

While the agent works in a terminal, its only interlocutor is the person at the keyboard. But an agent that embeds into editors must talk to different clients: IDEs, chat panels, third-party editors. Each client displays answers in its own way, each wants its own settings, and each confirms actions in its own way. If you write a separate integration for every client, the agent turns into a set of adapters.

The Agent Client Protocol (ACP) is the common protocol between an agent and a client: initialization, sessions, the stream of messages, tool calls, confirmations. Junie implements it and adds its own extensions on top of the base protocol. This chapter is about how such a layer is built, which rules keep it in order, and where it still "lies".

## 17.1. What ACP is

ACP describes a conversation between two parties. The client (the editor) opens a session, sends a request (`session/prompt`), receives a stream of updates (fragments of the answer, tool calls, permission requests), and at the end a result. The agent does the reverse: it answers requests and reports progress.

The project provides two transports: standard input and output for local launches, and a WebSocket transport (the package `transport/ws`) for remote ones. The transport is a detail: the protocol is the same.

Support appeared on 7 October 2025 ("add acp support"). The flag `--acp` in the CLI switches the mode on (Chapter 12). The first version was the only one. The second version, ACP v2, appeared in August 2026 ("emit message IDs for ACP content chunks", 4 August), and its contract for replaying a session was fixed in September 2026.

## 17.2. Two protocols in one agent

The main architectural detail: the agent hosts **two versions of the protocol** at the same time. The document `acp-extensions.md` describes the selection rule: with v2 routing enabled, the protocol is chosen by the **first `initialize` request**. Everything that arrives before it is handled as v1. If a client sends a `_providers/set` request before `initialize`, the session is immediately switched to v1, so that a client which waits for a response before initializing is not blocked.

The packages in the code reflect this split: `session/v2` (39 files) and `session/bridge` (44 files, of which only four mention v2). Specific classes — `JunieV2AgentSession`, `V2ApprovalCoordinator`, `V2ElicitationCoordinator`, `V2GoalCoordinator` — reproduce the functions of v1 in the new form.

Why keep two versions? Clients update at different speeds. An editor that works with v1 must not break because the agent has moved to v2. Dual support is expensive, but without it, upgrading the agent would mean upgrading all clients at once.

The lesson: **the protocol version should be selected during negotiation, not by a permanent setting**, and the transition must be safe for a client that does not yet know about the new version.

## 17.3. Extensions: the rule of "a negotiated capability"

The base ACP does not cover everything an editor needs. Goals (Chapter 18), confirmations with special forms, file reports, a list of sessions, model providers are needed. Junie adds them as **extensions**. The catalog in `docs/acp-extensions.md` lists dozens of such extensions, in tables running to hundreds of rows: for each one it gives the direction (agent to client or the reverse), the shape of the request and response, and whether Junie implements its side.

The key rule of the catalog reads:

> Gate on a negotiated capability, never on client identity.

That is, the decision whether to send an extension must rest on a capability the client has explicitly declared during negotiation, not on the client looking like an IDE of a particular vendor. Identity can be faked and changes; capabilities are declared and verified.

Around this rule there are three supporting ones:

- **A missing or malformed `_meta` must not break the standard output.** An agent that publishes no extensions still connects, answers, and renders. A client that does not understand them shows the base answer.
- **Vendor keys stay behind a namespace.** For example `claudeCode` or `jetbrains.air`. Only that vendor's decoder reads them, so foreign JSON never reaches the common session mapper.
- **Rejections carry a reason.** The error uses a standard JSON-RPC code, and `data.reason` gives the specific cause. A client that understands the reason can react to it; the others see an ordinary error.

These rules sound obvious. But the document has a section that makes it honest: the list **"Non-capability-gated hacks"**, that is, the violations of its own rule.

## 17.4. An honest list of debts

This section of the document deserves a detailed retelling, because it is rare to see a team list its own violations aloud. Here are nine items, abridged:

1. The notification `lastRequestComplete` assumes that the client understands the key. One of the clients decodes it only on the cloud path, so locally it is ignored.
2. The client's feature identifier is derived from the client's identity for analytics, without explicit opt-in. This directly contradicts the rule above.
3. The fallback reading of additional directories from `_meta` works when the standard field is absent. Version v2 does not read it, and the same keys in `session/prompt` are ignored. The divergence between versions is also a debt.
4. Live terminal streaming is switched on by the `terminal_output_delta` capability, but a fallback based on client identity remains until all clients have moved over.
5. The fields `_meta.junie` and `_meta.codex.phase` are present in every agent message without a capability that would explain them. Nothing decodes them yet.
6. The layout of the model list depends on the client's identity, not on a capability.
7. Nested subagents and asynchronous tasks are accepted from any agent, although the client declares them in its envelope. The declaration is an intention, not a gate.
8. The path to the plan file arrives together with the permission request, regardless of what the client declared.
9. A skill mentioned in a prompt as `$name` is loaded for any client, as in the CLI.

Why this matters for the book. Lists like this are rarely written in product projects, because they look like an admission of mistakes. But without them one cannot tell what will break when a client changes. The list works as a risk map: each violation can be closed by a separate ticket, and the document requires that new violations come only with a ticket.

The rule from the document: **a new exception to the capability rule is added only together with a ticket**. Exceptions are permissible, but they must be visible.

## 17.5. Parsing answers: Markdown normalization

One of the subtlest tasks is the ordering of the parts of an answer. The agent sends its answer in fragments, and each fragment is part of one message with one identifier. The client displays the fragments as they arrive. But Markdown does not split into fragments: an unclosed code block in one fragment changes the rendering of everything that follows.

The document `acp-markdown-normalization.md` solves this as follows: the normalizer sends the **known prefix** immediately and waits only when the next input could change that prefix. Text that can already be displayed unambiguously goes out without delay. Text that may still change waits.

There is also a detail that shows the level of care. The document describes that when a session is loaded (`session/load`), the answer is replayed through the same normalization as in a live stream: `normalizeMarkdownForAcp(text).trimEnd() + "\n\n"`. If the replay took a different path, a saved session and a live one would look different.

The lesson: **the same content must go through the same processing path, whether it arrives in real time or is restored from history**.

## 17.6. Session configuration: a boundary of ownership

Another document, `acp-session-configuration.md`, describes the boundary between logic and protocol. The configuration controller owns validation, state changes, model discovery, and the reconciliation of availability. It receives the session state and a string identifier, but it **does not receive the SDK session object**. Its API uses types that belong to Junie.

The point of the boundary: if the controller depended on the SDK, a change of SDK version would change the configuration logic. If it depends only on its own types, the SDK can be replaced and the logic kept. This is the same principle as the separation of the core and the IDE in Chapter 6.

Another example of the same rule: the validation of inputs for `_providers/set` is described in the document as a list of exact error texts (`providerId must be a string`, `baseUrl must be an absolute http or https URL...`). The exact texts are not cosmetic: a client may match them against interface fields, and any change of text breaks that parsing.

## 17.7. What changed since 2025

The chronology from the commits, in order:

- **7 October 2025** — ACP support in the CLI.
- **26 February 2026** — model availability becomes reactive; the configuration is sent to the client when it changes.
- **15 June 2026** — categories of the model and effort configuration options.
- **4 August 2026** — message identifiers for content chunks (the start of v2).
- **20 August 2026** — the document on the goal extension (Chapter 18).
- **2 September 2026** — the contract for replaying a session in v2 is fixed.

It is clear that in 2026 the work moved from "make it work" to "agree on a contract": versions, capabilities, catalogs, and documents.

## 17.8. What follows

1. **Negotiate protocol versions during the handshake.** The transition must not break a client that does not yet know the new version.
2. **Enable extensions by capability, not by client identity.**
3. **Missing fields must not break standard behavior.**
4. **Keep foreign vendors' keys behind a namespace** and decode them only with their own decoder.
5. **Explain refusals with a reason**, not only with a code.
6. **Keep a list of your own rule violations.** A new violation comes only with a ticket.
7. **One processing path for a live stream and for restoration** from history.
8. **Exact error texts are part of the contract.**

## Exercises

1. Implement a mini protocol: the client sends `initialize` declaring its capabilities, and the agent answers with its own. Then the agent sends an extension only if the client declared the matching capability. Verify that a client without the capability gets the base answer.
2. Add a protocol version: requests before `initialize` are accepted as v1, and after it as v2. Verify that a client sending a request before initialization is not blocked.
3. Write a refusal with `data.reason`. Verify that a client that understands `reason` shows the cause, while a client that does not sees a standard JSON-RPC error.
4. Start a "debt" document: for each violation of your rule, name where it is and the ticket that will close it. Add a rule that new violations are recorded only with a ticket.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The catalog of extensions is `docs/acp-extensions.md`, the normalization is `docs/acp-markdown-normalization.md`, and the session configuration is `docs/acp-session-configuration.md`. The list of violations of the capability rule is the section "Non-capability-gated hacks" of the same document, retold in abridged form.
