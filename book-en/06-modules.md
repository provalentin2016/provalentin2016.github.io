# Chapter 6. Modules: From Six to Twenty

[← Previous](05-reliability.md) · [Contents](README.md) · [Next →](07-execution-context.md)

An agent that lives in a single module quickly becomes a tangle. Model logic, file handling, the IDE interface, command-line startup, and network calls grow together, and any change touches everything. An agent that must work in the IDE, the terminal, and Slack cannot get by with one module. So the boundary between parts of the code is not a matter of taste: it is the condition under which the product can be extended at all.

In the history of Matterhorn the code was split into modules twice: in September 2024 and in June 2026. In between, the number of modules changed a great deal. This chapter is about which boundaries proved stable and which did not.

## 6.1. The first split: 13 September 2024

Until September 2024 everything lived in a single Gradle module of the plugin. The commit "Split Matterhorn into modules: core, ej-core, ej-ui, ej-idea, ej-pycharm, webgen" split it into six:

```kotlin
rootProject.name = "matterhorn"
include("core")
include("ej-core")
include("ej-ui")
include("ej-pycharm")
include("ej-idea")
include("webgen")
```

The purpose of each module, judging by the files that were moved:

- **core** — what does not depend on a specific agent or IDE: artifacts (`Artifact.kt`), the execution context (`ExecutionContext.kt`, `RootExecutionContext.kt`), shell handling (`ShellExecutor.kt`), LLM clients (`AISender.kt`, `AnthropicChatRequest.kt`, `OpenAIChatRequest.kt`), TeamCity logging (`TeamCityLogger.kt`), and project snapshots (`ProjectFileStructure.kt`, `ProjectStateHelper.kt`). The module gained `CommandLineStarter.kt`, 230 lines — an entry point without the IDE. This was the first attempt to run the agent from the command line, which later became the CLI.
- **ej-core** — the agent's logic on top of `core`.
- **ej-ui** — the interface of Junie in the IDE.
- **ej-idea** and **ej-pycharm** — adapters for specific IDEs.
- **webgen** — the project generator from Chapter 1.

The main thing about this split is the moving of classes, not new classes. The source code was mostly unchanged: the commit consists largely of move operations that preserve history; for example, `ProjectFileStructure.kt` was moved to another package. This is an important technique: move files without rewriting them, so that `git blame` history survives.

## 6.2. The rule of dependency direction

A split without a rule about direction quickly turns into a graph where everything depends on everything. The document `docs/junie-rd.md` records the rules (the file was last changed in July 2025, but the structure it describes is older):

- **core** must be a library that does not depend on the interface layer. It can be used on the frontend and the backend, but in Junie only on the backend.
- **ej-core** is a module reused by Junie and by the generator. It should provide only server-side functionality.
- **ej-ui** should depend only on `shared`, not on the backend and `ej-core`.

The document honestly notes that the current state departs from the rules: about ej-ui it says "for now it depends on backend, ej-core, backend-proxy, etc. should depend on shared only". Such an admission is more useful than an idealized scheme. The document also describes a temporary module `shared` inside `ej-core`: "temporary module which keeps Junie only classes that are needed for ej-core". Temporary modules are a common feature of large projects, and it matters to mark them as such.

What is visible in the current HEAD: the `core` module does not depend on `ej-core`, so the direction is respected. The nested modules `core:analytics`, `core:mcp`, and `core:vms` depend on `core`, which is normal. But `ej-core` uses `core.llm` directly in three files, and `ide-server` in thirty-nine. So the boundary between the agent and the IDE server leaks. This is not a catastrophe, but the rule "ej-core does not know about the IDE" is only partly followed in practice.

The practical conclusion: **the dependency-direction rule must be checked automatically**. The document describes it, but this history contains no architecture test that would fail on a violation. For your own project this can be done in an hour: a script that parses imports and compares them with a table of allowed dependencies.

## 6.3. Growth: from six to fifty

The number of modules in `settings.gradle.kts` changed as follows (snapshots by the date the file last changed):

| Date | Modules |
|---|---|
| September 2024 | 6 |
| March 2025 | 27 |
| May 2025 | 50 |
| September 2025 | 39 |
| February 2026 | 40 |
| October 2026 | 20 |

The growth from 6 to 50 coincided in time with the appearance of the CLI, the ACP server, and related infrastructure. Examples of modules that appeared in this period and are present in HEAD: `ej-app:cli-standalone`, `ej-app:cli-gateway`, `ej-app:cli-evals`, `ej-core-api`, `core:mcp`, `core:vms`, `core:analytics`, `core:a2ux`, `ide-server:api`, `ide-server:client`, `ej-chat-core`, `ej-integration-tests`. Each of them is responsible for one external contact: the CLI, MCP, metrics, the IDE server, Slack.

Note that modules were not only added but also merged. The drop from 50 to 20 came from removing the IDE line and from grouping nested modules. The number of modules is not a measure in itself: fifty modules may be wiser than six if each has a clear responsibility.

## 6.4. Build conventions

When there are many modules, identical Gradle settings get duplicated. In October 2024 the commit "Extract common code from build.gradle to plugin" moved the shared parts into a plugin of their own. The repository keeps this in the directory `buildSrc/src/main/kotlin/matterhorn/`. So the common build settings are defined once, and a module declares mostly its own dependencies.

Dependencies in the modules are read in a uniform way. For example, in the current HEAD `ej-core` pulls in `core`, `core:analytics`, `core:mcp`, `ej-core-api`, `core:vms`, `ide-server:api`, and `ide-server:client` through `implementation`, and for tests it adds `core:llm` and `core:llm-testing` through `testImplementation`. The difference matters: `testImplementation` does not leak into the module's consumers.

## 6.5. The IDE plugin: how to attach a module

While Junie was an IDE plugin, adding a module was harder than it is now. The instructions in `docs/adding-new-module.md` describe five steps:

1. Copy an existing module and rename its packages.
2. Create an XML descriptor with extension points, actions, and components.
3. Add a dependency in the plugin's Gradle module.
4. Add a `<depends>` entry in `plugin.xml` to set the loading order.
5. Add a `testImplementation`, otherwise the tests will not see the extension points.

The error the document describes as common: `Missing extension point ... (unit test)`. It appears when step 5 is skipped. The reason is that the IDE loads extension points from the plugin, and tests without the dependency do not see that plugin. This is a lesson about attachment mechanisms: in a plugin architecture a module exists not only in Gradle but also in the IDE's runtime, and the two worlds have to be kept in sync.

For an agent without an IDE such a mechanism does not exist, which simplifies the split. The cost is that you must decide yourself how the modules find each other.

## 6.6. Naming conflicts

Modules live in one project with the IDE, where there may be classes with similar names. In March 2025 the commits "rename components to avoid conflicts with AI Assistant" and "rename extension points to avoid conflicts with ej-core referenced from AI Assistant" appeared. The commit names the cause directly: AI Assistant in the same IDE referenced ej-core, and the names clashed.

The lesson: **extension point and service names are a public API, and they must be chosen with every plugin that will run alongside in mind**. The package `com.intellij.ml.llm.matterhorn` still remains in the code, but the extension points were renamed. Partial renaming is a typical compromise: public names change, internal ones stay, so that thousands of lines do not have to be rewritten.

## 6.7. What became of the modules in the current code

On 22 June 2026 the commit "Remove IDE plugin and IDE-only app/test modules" removed the IDE line. More than a thousand files were deleted: `ej-ui` (723 files), `ej-core-ide` (755), and `ide-core` (145). The modules `ej-idea`, `ej-pycharm`, and `webgen` are absent from HEAD.

What was preserved: the `core` / `ej-core` boundary survived, and in HEAD the CLI, ACP, MCP, and Slack modules stand on top of it. This matches the chapter's main conclusion: **an architecture divides into what changes when the outer shell changes, and what does not**. The removal followed the module boundaries: whole IDE modules disappeared, and the core stayed in place.

The other side: the boundary was not strict enough (see Section 6.2), and some IDE dependencies remained in the agent. In HEAD `ej-core` still imports `ide-server` in thirty-nine files, so the removal of the IDE modules was not complete.

## Exercises

1. Draw the dependency graph of your project: modules and arrows "depends on". Mark the arrows that violate the direction rule (for example, a lower layer knowing about an upper one).
2. Write a check that parses the imports in each module and fails if a forbidden import is found. Use the table of allowed dependencies from your graph. Test the check by adding a deliberate violation.
3. Extract one adapter (for example, the CLI or the interface of a particular messenger) into a separate module. Move the files with `git mv` to preserve history, and verify that the core builds without the adapter.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The state of `settings.gradle.kts` by date comes from the file's history. The removal of the IDE line was verified against HEAD (`git ls-tree`).
