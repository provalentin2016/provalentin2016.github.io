# Chapter 11. Names: Renaming Without Breaking Users

[← Previous](10-testing-nondeterministic.md) · [Contents](README.md) · [Next →](12-standalone-cli.md)

A product that grew out of an internal project almost always carries two names: a working (code) name and a public one. Matterhorn's working name was in every file, while its public name became Junie. The renaming took about two years and is still not finished. This chapter is not about how to name a product. It is about which names are easy to change, which are very expensive to change, and why.

The main conclusion: **the name in the code, the name in the interface, the name in the data, and the name in the external contract change at different speeds and with different consequences**. They must not be mixed up.

## 11.1. Chronology

The renaming went layer by layer, and the order is visible in the history:

- **12 November 2024** — the plugin was renamed (the commit "rename plugin").
- **5 December 2024** — a user-facing string: "Collect Matterhorn Logs and Diagnostic Data" became "Collect Junie Logs". This was the first change visible to users.
- **10 March 2025** — "Rename components to avoid conflicts with AI Assistant". Components were renamed so as not to conflict with another plugin in the same IDE. More on the conflict in Section 6.6.
- **15 July 2025** — the CLI repository was renamed (the commit "update junie cli repo name").
- **15 October 2025** — the commit "introduce junie home" introduced the `JUNIE_HOME` directory for user data. At the same time, the CLI-in-IDE mode was removed from the code.

It is clear that the renaming went from the outside in and from the IDE toward the CLI. The first things renamed were what the user sees; the last were what only programmers see. Internal packages were not renamed at all.

## 11.2. What stayed in place

By November 2026, "matterhorn" appears in the file paths of 5,763 files in HEAD. The main reason is package names: `com.intellij.ml.llm.matterhorn` appears throughout the code, from `core` to `ej-app`. The XML descriptors of modules are called `matterhorn.core.analytics.main.xml`. Renaming the packages would mean renaming thousands of files and losing the `git blame` history of many lines, so the packages were left alone.

This is a reasonable compromise, but it has a cost. A new developer sees two names and must know which one is public. Documentation that uses "Junie" may refer to classes with "Matterhorn" in their names. Any "rename in one action" is out of the question here.

The rule that follows: **internal names can be left alone if they are not visible to the user and do not take part in an external contract**. A package is internal. A string in the interface is visible. An environment variable is a contract.

## 11.3. A clash of namespaces

Why was renaming the components urgent? Because the IDE is a shared space. Extension points, services, and action identifiers are registered globally, and two plugins with the same extension point name break each other at load time. The error does not show up immediately: the plugin loads, but one of its components is not found or the wrong one is found.

The lesson for your own project: **public identifiers should be chosen with a prefix unique to your product**, and checked for conflicts with neighboring products before the first release. Renaming an identifier that has already been published costs more than naming it correctly from the start.

## 11.4. Data and environment variables

The most instructive place is the environment variables. They are an external contract: users and CI configure them by hand, and changing a name breaks other people's configurations. Let us see how things stand in HEAD.

The new prefix `JUNIE_` is used in 212 files (`JUNIE_HOME`, `JUNIE_DATA`, `JUNIE_API_KEY`). The old `MATTERHORN_` remains in 40 files: `MATTERHORN_TOKEN_TYPE` (first appearance June 2025), `MATTERHORN_CAN_READ_FROM_REDIS` and `MATTERHORN_CAN_WRITE_TO_REDIS` (the cache from Chapter 10), `MATTERHORN_GRAZIE_ACCESS_TOKEN`.

The most interesting file is `CoreProperties.kt`. There a property is declared in code like this:

```kotlin
val MATTERHORN_GRAZIE_USER_ACCESS_TOKEN: MatterhornProperty = prop(
  ...
  "MATTERHORN_GRAZIE_ACCESS_TOKEN"
)
```

The property's name contains the word `USER`, while the string the program reads from the environment does not. The internal and the external names have already diverged, and nobody has aligned them. This is safe as long as the external name does not change: the internal name can be renamed, the external one cannot. The difference is visible in a single line.

In the file `JVMSpawnShellExecutionEnvironment.kt`, one and the same mechanism uses both prefixes: `JUNIE_DISABLE_SESSION_DETACH` and `MATTERHORN_SESSION_ID`. The transition is not complete, and that is normal: each variable migrates on its own, when someone gets to it.

A similar story exists with serialization. In Chapter 2 we saw that the class `LastNObservationsResponse` kept `@SerialName("Last5ObservationsResponse")`. Stored data refers to the old name, and if it were changed, previously recorded histories would stop being readable. This is the same rule as for variables: **a name that reaches the disk or the network is a contract**.

## 11.5. How to rename external names

Three practical rules follow.

**First: read the old and the new name at the same time.** The variable `JUNIE_X` is read, and if it is absent, `MATTERHORN_X` is read. This allows a gradual transition. For a project starting a rename, this is a mandatory condition.

**Second: write only the new name, but read both.** The program never writes the old name, but it accepts it. After several releases the old name can be removed, and by then it no longer appears in any new configuration.

**Third: record the mapping.** A table "old → new → when" is needed not only in the documentation but also in tests. A test that checks that the old variable is still read protects against accidental removal. In HEAD, 18 test files use `MATTERHORN_` names, but I did not find a test that explicitly checks the fallback reading of the old name during the transition. If no such test exists, the transition rests on convention rather than on verification.

On serialization separately: if a class name changes but the serialized name is kept (as with `@SerialName` in Chapter 2), the data remains readable while the code looks new. This is not a gap but a normal way to separate the internal name from the external one.

## 11.6. The user data space

The chronology of the `JUNIE_HOME` directory reveals another thread: where the user's data lives. The commit of 15 October 2025 introduced a single directory for logs, settings, sessions, and versions. The document `docs/junie-cli-user-disk-storage.md` lists everything that lives there: logs, `settings.json`, versions, sessions, the cost cache, `teleport`, attachments, processes.

Moving data is a heavy operation. If the directory changes, the data of the old version is either lost or needs a migration. The storage document exists precisely so that a migration is understandable: what lives where, and what can be deleted safely.

## 11.7. A renaming checklist

If you are renaming your own project, check in this order:

1. **List the names by layer**: packages, classes, interface strings, environment variables, configuration files, data on disk, network protocols.
2. **For each layer decide**: change now, change later, or not change at all.
3. **For external names**: read both variants, write only the new one, keep a mapping table, and test the old name.
4. **For serialization**: keep the old name in `@SerialName` or an equivalent, for as long as data exists.
5. **For IDEs and shared platforms**: check for conflicts of extension points and identifiers.
6. **For data on disk**: describe the directory and the migration before moving anything.
7. **Do not rename packages for the sake of tidiness.** The cost is the `git blame` history and thousands of changed lines. The benefit is almost zero for the user.

## Exercises

1. Take an environment variable with a code name and rename it to the new one. Implement reading of both variants: the new one takes priority, and the old one works with a warning in the log.
2. Write a test that checks that the old variable is still read. Then remove it from the documentation and make sure the test still passes.
3. Serialize an object whose class is named `ResultV2`, but keep the stored `@SerialName("Result")`. Rename the class to `AnswerResult`. Check that old JSON on disk is still readable.
4. Draw up a table "layer → name → decision" for your own project: what to change now, what later, and what to leave alone.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The file and prefix counts were obtained from HEAD through `git grep`. The storage document is `docs/junie-cli-user-disk-storage.md`.
