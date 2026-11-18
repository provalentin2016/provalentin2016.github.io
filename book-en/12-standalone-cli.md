# Chapter 12. From the IDE to the Terminal: Standalone and CLI

[← Previous](11-naming-and-rename.md) · [Contents](README.md) · [Next →](13-mcp-and-ide.md)

For the first year and a half the agent lived inside the IDE: from March 2024 to July 2025. It saw the open files, the project index, the tool panel, and the single user sitting in front of the screen. To turn the agent into a product that can be launched in a terminal, in CI, in an editor through a protocol, or in Slack, it had to be separated from the IDE. This chapter is about how that was done, which parts moved, which stayed, and why the hardest part turned out not to be the agent but the launch.

## 12.1. What "standalone" means

Standalone is not simply "a CLI without a window". It is a separate application with no IDE as its host: it reads its own configuration, stores its own sessions, presents its own interface, and updates itself. The module `ej-app/cli-standalone` grew out of the first commit, "Junie standalone project scaffolding" (16 July 2025). In HEAD it contains about 3,800 files.

The package structure shows how the responsibilities were distributed. The largest groups:

| Package | Files | Responsibility |
|---|---|---|
| `tui` | 585 | the terminal interface: screens, input, slash commands |
| `acp` | 385 | the protocol for editors (Agent Client Protocol), Chapter 17 |
| `framework` | 71 | the application's shared scaffolding |
| `utils` | 62 | helper utilities |
| `ide` | 39 | a bridge to the IDE, when one is present |
| `extensions` | 38 | extensions |
| `sandbox` | 30 | the sandbox, Chapter 15 |
| `gateway` | 28 | a gateway for multi-user scenarios, Chapter 19 |
| `migration` | 22 | data migration between versions |
| `session` | 20 | sessions: saving and resuming |
| `trust` | 17 | trust in a project |
| `allowlist` | 14 | allowed actions, Chapter 8 |
| `updates` | 13 | updating and restarting the application |

The interface and the protocol take up most of the module. The agent itself is the core in `core` and `ej-core` (Chapter 6). Standalone is the shell around it: without the core it does not work, but the core without the shell is not a product.

## 12.2. One binary, several modes

The entry point is `Main.kt`, with the function `main(vararg args)`. It decides which mode to run in. There are several modes:

- **interactive** — the TUI, by default;
- **ACP** — the flag `--acp` for editor integrations; it appeared in October 2025, together with the first ACP support;
- **headless** — a non-interactive run of a single task for scripts and CI;
- **gateway** — a separate gateway process that accepts clients over the network (it is built as a separate module, `cli-gateway`).

A single binary with modes was chosen deliberately: one set of dependencies, one version, one configuration. The price is startup time and size. The parameter documentation shows how the modes are selected through flags and environment variables (`JUNIE_ACP` is equivalent to `--acp`).

`Main.kt` reveals one more detail: environment variables and arguments are logged at startup. The function `startupLogEntries` writes them to the log, and the separate flags `--dump-env-vars` and `--dump-cmd-parameters` print them for diagnostics. This is useful when a user says "it doesn't work" and nobody knows which settings were actually applied.

## 12.3. The directory on disk

A standalone application has to keep its state somewhere other than the project. Since October 2025 that place is `JUNIE_HOME` (Chapter 11). Logs, settings, versions, sessions, and caches go there. The document `junie-cli-user-disk-storage.md` lists the subdirectories, including `teleport/`. The command `/teleport` appeared on 3 November 2026: it packs the conversation, the checkpoints, and the uncommitted code into a git bundle, but without the values of environment variables. This way a session can be continued on another machine without leaking secrets.

The interesting choice here is what is **not** packed. Environment variables contain keys, and they must not be transferred. Uncommitted code is transferred, because work cannot continue without it. The boundary is drawn explicitly and written down in the documentation, rather than being left to the user's judgment.

## 12.4. Restart and update

An agent that works for hours sooner or later needs an update. Restarting a process is not an obvious operation: you have to save the session, release the terminal, and start the new version in such a way that it picks up the state. The mechanism `ProcessRestart` appeared on 8 October 2026 ("Feat Restart Command"). It works through a file whose path is passed in the environment variable `JUNIE_RESTART_FILE`. The old process atomically writes the session identifier and the project path into the file (first to a temporary file, then by renaming it). The new process reads the file when it starts. A restart requires launching through the managed launcher: without it, the code reports the error explicitly.

The file-based scheme is a typical compromise for a cross-platform application. Restarting through `exec` does not work everywhere, especially on Windows. A file is simpler, but it has to be validated: a stale or corrupted file must not start the wrong session. Atomic writing is needed so that the new process never reads a half-written file.

## 12.5. The native launcher: why Java's own launcher was not enough

The most unexpected part of standalone is the launcher. Junie is distributed as a package that contains a JVM and the application. The package is created by jpackage, which also creates the standard launch file. That file does three things: it finds the JVM, passes it parameters, and starts the application. The problem is that such a launcher has no clear behavior in two respects: the process gets a different name (in the process list it does not appear as `junie`), and environment variables such as `JDK_JAVA_OPTIONS` affect the startup in unexpected ways.

So in November 2026 the repository acquired `native-launcher/`, a small program written in Rust. Its README states the contract directly. The launcher loads `libjli.dylib` from the bundled JVM and starts the JVM **in its own process** through `JLI_Launch`. The process remains the same: the same name, the same PID, the same exit code, the same reaction to signals.

The details of the contract show how many small things have to be taken into account:

- the launcher finds its real path through `realpath`, so that it works through symbolic links;
- the JVM parameters are read from the file `jvm.options`, not from a built-in list;
- the mandatory parameters (`--enable-native-access=ALL-UNNAMED`, the path to the application) are always added, and they come **after** the user's parameters so that they cannot be overridden;
- on macOS, `JLI_Launch` re-enters `main` from a new Java thread, and the launcher must recognize that.

Why Rust and not Kotlin/Native? `AGENTS.md` states that Kotlin/Native adds a garbage collector and threads, and does not support all the required platforms (for example, Windows arm64). The decision is deliberately made against stack uniformity. The language of the launcher is not a preference but a consequence of platform constraints.

The lesson for your own agent: **if you ship an application with a JVM or another runtime, the launching file is part of the product**. Its behavior with the process name, the signals, and the environment variables is noticed by users earlier than bugs in the agent.

## 12.6. What follows

1. **Standalone is the shell around the core.** The agent's core does not change because the application is now in a terminal. The interface, the storage, and the launch change.
2. **One binary with modes** is easier to maintain than several products, but it starts more slowly.
3. **State is a separate directory**, and the boundary between what is transferred and what is not must be explicit.
4. **Restarting through a file** is simpler than `exec`, but the file must be written atomically and validated.
5. **The launcher is part of the product.** Its contract with the operating system has to be described and verified.
6. **Diagnostics at launch.** A log of parameters and a dump of the environment pay off at the first support request.

## Exercises

1. Build a simple CLI agent with two modes: interactive and headless (one task from an argument). The shared core must be a single module. Verify that the core does not depend on the input method.
2. Implement session transfer: pack the conversation history and the uncommitted changes into one file, without including environment variables. Verify that the session restores on a clean copy of the project.
3. Implement a restart through a file whose path is passed in an environment variable. Write through a temporary file and a rename. Check three cases: the file is valid, the file is missing, the file is corrupted. In all three the new process must start, and only in the first does it restore the session.
4. Run the application through the standard launcher and through your own minimal one (it can be written in any language that starts a process with the required name). Compare the process name and the reaction to `Ctrl+C`.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The package structure and file counts were obtained from HEAD. The launcher contract comes from `native-launcher/README.md`; the CLI parameters come from the documentation in `documentation/by-source/`.
