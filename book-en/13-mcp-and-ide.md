# Chapter 13. Tools From Outside: MCP and the IDE as a Tool Provider

[← Previous](12-standalone-cli.md) · [Contents](README.md) · [Next →](14-context-management.md)

The agent can read files, edit them, and run commands. But real tasks need other capabilities too: a database, GitHub, a browser, documentation, the build, the IDE's debugger. Writing a dedicated tool for each one inside the agent's core is a dead end: the core bloats, and every integration requires a new product version.

The MCP protocol (Model Context Protocol) solves this differently: an external server declares its own tools, and the agent connects to it as a client. This chapter covers two sides of the idea. The first: Junie as an MCP client that connects external servers. The second: the IDE as an MCP provider that gives the agent its own capabilities. Each side has its own difficulties, and both are clearly visible in the history.

## 13.1. Junie as an MCP client

The client lives in the module `core/mcp`. Its classes show what an integration consists of: `McpClient`, `McpClientService`, `McpTool`, `DiscoveredMcpTool`, `McpServerConfiguration`, and, for authorization, `OAuthAuthService`, `OAuthAuthorization`, `McpOAuthDiscovery`.

A server connects in one of two ways, and this is fixed in the type `McpServerType`:

- **Local** — a process on the user's machine, communicating through standard input and output;
- **Remote** — a hosted server over HTTP or HTTPS.

The first commit of the integration is "Added mcp server integration" from 20 May 2025. The server configuration is stored in the file `mcp.json` in the `.junie/mcp` directory of the project, or in the user's home directory. The schema of this file has changed: the change of 23 June 2025 ("Changed mcp settings schema") shows that the configuration became a subject of migrations right away, and that is correct: the file format is an external contract (Chapter 11).

A separate detail concerns process arguments. The commit "Preserve mcp arguments with quoting" (14 August 2025) fixed the loss of quoting when a local server was launched. Judging by the title, the problem was that an argument containing a space could split into pieces when passed through a shell. Such errors are invisible on a test server and break life for users whose paths contain spaces. The lesson: process arguments should be passed as a list, not as a string that someone will later parse.

## 13.2. The problem: too many tools

The main difficulty of MCP is not the protocol but the budget. Each server brings its own tools, and each tool is a description that goes into every request to the model. Ten servers with ten tools each means a hundred descriptions in the context. The model spends money and attention on them, and it chooses a tool worse when there are many options.

Junie's answer is a capability filter. An agent responsible for selection sees the list of installed servers and the task, and decides which servers are needed right now. The class `CapabilityFilterExecutor` first appears in the history on 11 February 2026. Its result (`CapabilityFilterResult`) determines which tools reach the agent's context.

The asymmetry here matters: the filter can be wrong. If the needed server was not in the selection, the agent cannot use it, even though it is installed. That is why there is a tool for this case, `enable_mcp`, which appeared on 6 February 2026.

Its description in the code states the rules directly:

> Enable an MCP server that was filtered out by the capability filtering agent. Use this tool when you need tools from an MCP server that is installed but currently unavailable.

The tool works only for servers that are installed and were filtered out. If the server is not installed, the tool honestly answers "is not installed". If the server is already available, it answers "should already be available". Every refusal explains its reason. This is an important property: a tool that silently does nothing costs hours of debugging later.

The model gets two levels of access: the usual selection by the filter, and explicit enabling on request. This saves context, and the agent is not locked into a wrong selection.

## 13.3. Authorization: OAuth in the agent

Servers with remote access require authorization. OAuth support appeared in December 2025 ("Refactored mcp oauth flow implementation", 6 December), and already on 12 December the OAuth code was moved to another module (according to the commit message, `ej-core-id`). A move a week after a refactoring suggests that the first placement of the code was a poor fit: authorization belongs to the application's infrastructure rather than to the core of the MCP client.

Caution is needed in one place. The commit "narrow MCP OAuth client_secret_post fallback" (October 2026) narrowed the fallback authorization path: instead of any possible scheme, only `client_secret_post`. Expanding the list of permitted authorization methods is convenient, but every new permission is a potential hole. Narrowing it is the right move here.

## 13.4. Tool results: size matters

An MCP tool can return a gigabyte of text. If it is put into the context as is, the model loses everything else. So MCP actions have a threshold: `MCP_SUMMARIZATION_THRESHOLD`. A long result is collapsed into a summary. The constant appeared in the history in March 2026, together with support for structured output.

This is the same technique as for the built-in tools in Chapter 8 (a threshold of 10,000 characters). The difference is that MCP servers are third-party: their outputs are unpredictable. The threshold is a protection against foreign code, which also saves money.

## 13.5. The IDE as a tool provider

The second side: the IDE gives the agent what only it knows. The build, the debugger, the project structure, the symbols, the VCS status: all of this lives in the IDE and almost nowhere else. The module `ide-server` is the RPC layer through which Junie talks to the IDE.

The way it is built is interesting. Services are not written by hand but described by a schema in a dedicated DSL. The file `ide-server/README.md` shows that a new service starts with a schema file, in which records and their fields are described:

```kotlin
val DoSomethingRequest = record("DoSomethingRequest") {
  string("input")
  int("limit", default = "10")
  bool("verbose", default = "false")
}
```

The client and the server are generated from the schema. In the repository this is visible from the file names: `JunieBuildService`, `JunieBuildServiceClient`, `JunieBuildServiceServer`, as well as `JunieChroniclesService` and `JunieAndroidService`. For the build service all three files are present, and they agree with each other because they are generated from one description.

Generation protects against a typical mismatch: the client and the server diverge in a field or in a default value, and the error appears only at call time. The price is the complexity of the generator and the need to remember that changes are made in the schema, not in the generated code.

Since January 2026 the IDE has provided tools to the agent through MCP. The commit "created ide-core architecture and introduce MCP toolsets in ide-server" (9 January 2026) introduced this architecture. The idea is the same as for external servers: the tools are described by the protocol, and the agent does not know them in advance. The difference is that the server is the IDE itself, and its tools depend on the open project.

This gives the agent access to capabilities an external server does not have: for example, to the IDE's own debugger. But it also creates a dependency on the IDE: without it, the tools do not work. This is the link to Chapter 6, where the boundary between the core and the IDE modules was the subject of a decision.

## 13.6. What changed in 2026

A summary of the chronology:

- **20 May 2025** — the MCP integration in the client.
- **23 June 2025** — the schema of `mcp.json` changes; the configuration becomes a contract.
- **14 August 2025** — quoting in process arguments fixed.
- **6 December 2025** — OAuth for MCP.
- **9 January 2026** — MCP tools of the IDE in `ide-server`.
- **6 February 2026** — `enable_mcp` for servers filtered out by the capability filter.
- **11 February 2026** — the capability filter appears in the history as `CapabilityFilterExecutor`.
- **2 March 2026** — collapsing long MCP results.
- **October 2026** — narrowing of the authorization methods.

It is clear that 2025 went into connecting, and 2026 into governing: how many tools the agent sees, who decides what to enable, and what to do with large responses.

## 13.7. What follows

1. **Move tools out of the core.** The MCP protocol makes it possible to add capabilities without a new version of the agent.
2. **The tool budget is a budget too.** Every description costs context, so selection is needed.
3. **The filter can be wrong.** An explicit way to add a tool on request is needed, and refusals must explain their reasons.
4. **Pass process arguments as a list**, not as a string.
5. **Keep authorization separate** from the protocol client, and widen the list of authorization methods carefully.
6. **Collapse large responses** regardless of whose tool produced them.
7. **The schema is the source of truth for RPC.** The client and the server are generated from one description.

## Exercises

1. Connect two MCP servers (simple ones you write yourself): one with three tools, the other with ten. Count how many descriptions go into each request to the model.
2. Implement a filter that selects one of the servers per task. Test the case where the needed server was not in the selection, and add an `enable_mcp` tool that enables it. The refusal for a server that is not installed must explain the reason.
3. Pass an argument containing a space to a local server: first as a string, then as a list. Verify that in the second case the argument arrives intact.
4. Write an RPC service from a schema: describe a record with fields and default values, and generate a client and a server from it. Verify that changing a default value in the schema reaches both the client and the server.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The classes and modules were checked against HEAD. The description of the `enable_mcp` tool comes from the source code. The RPC schema comes from `ide-server/README.md`.
