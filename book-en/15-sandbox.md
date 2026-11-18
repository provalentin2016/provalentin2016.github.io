# Chapter 15. The Sandbox: Constraining the Agent Without Paralyzing It

[← Previous](14-context-management.md) · [Contents](README.md) · [Next →](16-multi-model.md)

An agent that runs commands in a terminal can do anything to the machine that the user can do. It can delete files outside the project, read keys from `~/.ssh`, download a stranger's script and run it. Usually this is prevented by confirmations (Chapter 8): the agent asks for permission for every command. But confirmations quickly turn into noise: if the user clicks "yes" a hundred times during a task, they stop reading. What is needed is another layer: a sandbox that limits what a command can do, regardless of what the user approved.

This chapter describes how the sandbox works in Junie, what it protects, where its boundaries are, and why its delivery turned out to be harder than the idea itself.

## 15.1. The idea: constraints at the process level

The sandbox wraps every command of the agent in an external tool, `srt` (sandbox-runtime). The command runs with constraints: which directories may be written, which may be read, which network sockets may be opened. The constraints operate at the level of the operating system, so they cannot be bypassed simply by rewriting the command.

The difference from confirmations matters here. A confirmation answers the question "may this be done?". The sandbox answers "what can this do, even if it was allowed?". The two layers complement each other: confirmation for non-obvious decisions, the sandbox for what must not be allowed by default.

The mode is switched on with the flag `--sandbox` or the command `/sandbox`. The first version appeared on 16 September 2026 ("Add opt-in terminal sandboxing to Junie CLI"). The word "opt-in" in the title is deliberate: the sandbox is off until the user turns it on.

## 15.2. The default policy

What is allowed is set by a policy file. The default values are visible in the code of `SandboxPolicyDefaults`. Writing is allowed in the project (`${PROJECT_DIR}`), in temporary directories (`${TMPDIR}`, `/tmp`), and in the tool caches: `~/.cache`, `~/.gradle`, `~/.m2`, `~/.npm`, `~/.cargo/registry`, `~/.rustup`, and others. The list is long, and this is deliberate: without the caches, every build would download its dependencies again, and the agent would become useless.

Reading works differently. The directory `~/.ssh` is denied as a whole, but three files from it are explicitly allowed: `config`, `known_hosts`, and `known_hosts2`. The reason is pragmatic: the agent needs to know which hosts to connect to, but must not read private keys. The boundary is drawn by the purpose of the files, not by the directories.

Notice how the rules are structured: by default everything that is not listed as allowed is denied. The opposite rule ("everything is allowed except…") quickly becomes a hole, because new dangerous places appear all the time.

## 15.3. The policy file must not be edited silently

The most delicate part is the protection of the policy itself. If the agent could change the file that defines its constraints, the sandbox would be pointless: the agent would simply allow itself everything.

That is why `SandboxActiveContext` has a dedicated mechanism. The rule is written in the function `authorizeEdits`:

```kotlin
if (paths.any { SandboxPolicyEditGuard.isPolicyTarget(policyFile, it) }) {
  val isSoleDirectTarget = paths.all { SandboxPolicyEditGuard.isDirectTarget(policyFile, it) }
  return if (isSoleDirectTarget && sandbox?.policyEditor != null) EditAuthorization.Allowed
  else EditAuthorization.Denied(...)
}
```

Editing the policy file is allowed only under three conditions: the path exactly matches the policy file, it is the only target of the edit in the request, and the edit has passed explicit confirmation. The check takes symbolic links into account: `isDirectTarget` refuses if the target is a symlink, and `isPolicyTarget` compares files through `isSameFile`, not just by the string of the path. Otherwise a bypass would be possible: a link with a different name would point to the same policy file.

This case is revealing. A protection must consider not only what the agent says, but also how the file system interprets the path. Comparing paths as strings is the most common hole in such a check.

## 15.4. What "literal arguments" means

Commands in a terminal are strings, and the shell interprets them. The argument `$(rm -rf ~)` inside a string becomes a command if it is not escaped. That is why a structured mode was introduced for the sandbox. Its contract is recorded in `docs/sandbox-srt-bundling.md`, very candidly:

> The pinned runtime still executes shell strings on macOS and Linux. The guarantee is literal arguments through the adapter, not shell-free execution.

So the guarantee is that **arguments are passed literally**: each argument is encoded with full POSIX escaping in single quotes, and apostrophes and substitutions remain data. But the command itself is still executed by a shell. The document states plainly that execution without a shell is not guaranteed.

Honesty in the wording matters. A sandbox without a shell would be stronger, but it did not exist. The document records what is guaranteed and what is not yet. A reader who takes "execution without a shell" for granted would be surprised.

The separation we met in Chapter 8 is visible here too: structured commands (arguments as a list) versus string commands. String commands are needed for deliberate shell programs, such as the diff. They are not removed, but they are marked separately.

## 15.5. Delivery: why the system-wide srt was not enough

The idea of a sandbox is simple. Delivering it is not. The tool `srt` is an npm package running on Node. If the user installs it by hand, a dependency on Node appears, and an application launched from Finder often cannot see `node` in `PATH`. So Junie ships its own build of `srt` inside the package.

The solution: `bun build --compile` builds a single binary from a fork. The document gives concrete figures: the arm64 binary weighs 60.7 MB, and the check "a write outside `allowWrite` is denied" passed. The binary is built in a separate repository and published as a release. Then the macOS and Linux packages verify and sign it.

The chain of several steps (building, publishing the release, verifying, packaging, and signing the package) is in effect a separate project. The document describes it in ten sections, from the structure of the contract to troubleshooting. For an agent this is a typical picture: the hardest part is not the logic of the constraints, but making sure the binary ends up on the right machine with the right version.

The versions are pinned as well: macOS keeps `0.0.71-jb.1`, while Linux and local downloads use `0.0.71-jb.2`. Pinning is needed because a new version of `srt` may change how the constraints behave, and checks made against an old version would stop meaning anything.

## 15.6. Status: what is enabled and where

The document states the status plainly: **EAP**. The sandbox is enabled in EAP, nightly, experimental, and development builds for macOS and Linux. It is not shipped for GA, and on Windows the flags `--sandbox` and `/sandbox` are hidden, with the mode remaining off.

This is the right decision. A sandbox is expensive to support and new, and its failures are invisible: a command simply fails with an unclear message. That is why it is released gradually, channel by channel, while reports of violations are collected. The code has `SandboxViolationMonitor` and a store of violation reports for this purpose (`SandboxViolationStore`).

Separate Linux support appeared on 25 September 2026 ("Support Linux sandboxing through the existing SRT integration"). The document lists the Linux system requirements and the policy for Unix sockets separately. This is a typical sign: the same constraint on different operating systems requires different system conditions.

## 15.7. What the sandbox does not do

An honest list of boundaries matters more than a list of capabilities:

- **It does not execute without a shell.** See Section 15.4.
- **It does not work on native Windows.** The adapter provides neither a sandbox nor a WSL backend.
- **It is not verified on every environment.** The document says plainly that Linux and native Windows were not covered by the same validation as macOS.
- **It does not replace confirmations.** A command allowed by the policy can still be harmful inside the allowed directories: for example, it can wipe out your own project. For this, confirmations and edit versions are needed (Chapter 8).

The last point is important for your own agent. The sandbox protects against leaving the boundaries, but not against mistakes inside them. A project that the agent deleted entirely is still inside `${PROJECT_DIR}`, and the sandbox will not save it.

## 15.8. What follows

1. **The sandbox is an additional layer on top of confirmations**, not a replacement for them.
2. **By default, deny everything that is not listed as allowed.**
3. **Protect the policy file** from editing by the agent, taking symbolic links and `isSameFile` into account.
4. **Document the guarantee precisely.** "Literal arguments" and "execution without a shell" are different claims.
5. **Pin the version of the tool** on which a constraint depends.
6. **Release by channel.** EAP, then GA, and only after data on violations has been collected.
7. **Describe the boundaries honestly**: which operating systems were verified, and what is not covered.

## Exercises

1. Implement a check of a path against the allowed directories for writing. Verify four cases: a path inside the project, a path in `/tmp`, a path in `~/.ssh`, and a path that leads into the project through a symbolic link from `/tmp`. The last one must be allowed only if the link points inside the project.
2. Write a protection for the policy file: an edit is allowed only with an exact path match and without a symlink. Verify that creating a link with a different name and editing through it are both refused.
3. Pass the argument `$(echo hi)` to a command first as a plain string, then escaped with single quotes. Verify that in the second case the substitution remains text.
4. Make a list of "what the sandbox does not protect" for your own agent. For each item, name the layer (confirmation, versions, backups) that covers it.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The default policy is in `SandboxPolicyDefaults.kt`, the protection of the policy in `SandboxActiveContext.kt`, the contract and status in `docs/sandbox-srt-bundling.md`. Quotations from the document are abridged.
