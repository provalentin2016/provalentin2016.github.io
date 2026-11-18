# Chapter 5. Reliability: An Agent That Fails Correctly

Chapters 1–4 described how the agent does its work. This chapter is about what happens when the work goes wrong: the network drops, the model returns 429, the `npm install` command hangs, the user presses "Stop", the budget runs out, and the agent is in the middle of editing a file.

For a demonstration agent these are minor issues. For a product that runs every day they are a large part of the code. Judging by the commit titles in the history of Matterhorn, errors, cancellation, retries, and state come up very often. I did not measure the exact share.

## 5.1. Four classes of failure

Before fixing anything, Matterhorn separated failures by their nature. The history shows four classes:

| Class | Example | What to do |
|---|---|---|
| Transport | timeout, dropped connection, 5xx | retry with a delay |
| Provider limits | 429, 529 | wait and retry, but not forever |
| Environment | a hung command, a failing `npm install` | limit by time, interrupt, return the error to the agent |
| Logic | the model returned the wrong format, an edit did not apply | return the error to the model (Chapter 2) |

The main mistake of the early versions was mixing the classes. Retrying a request after a logic failure wastes money and does not help. An environment error returned to the model as a "format error" confuses it.

## 5.2. The network: retries that must not be infinite

The first commits date from April 2024. `Retry failed HTTP requests automatically` (3 April 2024). The implementation relied on Ktor's built-in mechanism:

```kotlin
install(HttpRequestRetry) {
  retryOnServerErrors(maxRetries = 5)
  exponentialDelay()
}
```

The key here is `exponentialDelay()`: the delay grows with each attempt, so a series of retries does not overwhelm the provider. The commit of 8 April 2024 added retries for timeouts as well. The commit of 26 April 2024 set an explicit timeout of five minutes and switched from the Java client to the CIO client. The reason is not given in the message. Five minutes for a single HTTP request suggests that model responses could be very long.

The next class of failure is a dropped connection. `Retry if EOF exception occurs. Include response body to the message if status is not OK` (19 June 2024). Two actions in one commit: retry on EOF, and include the response body in the error message. Without the body, a 400 error becomes "HTTP 400", and there is no way to diagnose it.

Retries for Anthropic were not configured at first. `Add retries to anthropic call` (12 October 2024) and `Reuse existing service for HTTP client, retry for Antropic too` (12 October 2024) added them. The message of the second commit describes a concrete symptom: "I got empty header exception constantly without retry". Without a retry, an empty header broke the work constantly.

## 5.3. Provider limits: 31 October 2024

The most revealing episode is the rate limit. On a single day, 31 October 2024, two commits appeared, and their order is visible from their titles:

1. `infinite retries for anthropic rate limit errors`. The decision: on 429 or 529, wait 5 seconds and retry, with no limit.
2. `Add max retries in case of rate limit`. Right after the first: a limit of 1000 attempts for rate limiting.

Infinite retries turned out to be a bad idea. An agent that waits for a limit forever can hang for hours, and the user sees no reason. The limit of 1000 is also a large number, and the history contains no justification for that exact value. It may have been chosen as "large enough not to trigger under normal conditions, but not infinite".

The lesson for your own implementation: **a retry without a limit is not a policy, it is the absence of one**. The limit, the delay, and the message to the user must be set explicitly. Note that in these commits the delay is fixed at 5 seconds; there is no exponential delay for rate limits in them.

## 5.4. Cancellation: the Stop button must work

The Stop button is what the user presses when the agent has gone the wrong way. It must stop everything that is running and must not leave half an edit on disk.

The first version was incomplete. `Cancel leaf nodes as well as their parents when a user clicks on Stop button` (2 April 2024). Stopping cancelled the leaves of the task tree but not their parents. A week later: `Cancel unfinished nodes in case of exception` (8 April 2024). An error in one node must also cancel the unfinished nodes; otherwise they keep running as orphans.

Then a subtler problem appeared: cancellation was signaled through the `CancellationException`, which was used both for stopping and for other purposes. The commit of 13 November 2024 says: "do not use cancellation exception to cancel generator, use special type of exception to gracefully handle exception". Cancellation and error are different things, and mixing them causes code that should have finished cleanly to swallow the signal silently.

One more step: `CancellableArtifact support` (10 December 2024) and `Support artifact execution cancellation in favor of other artifacts` (10 December 2024). An artifact can cancel itself in favor of another: if a result for the same task already exists, a duplicate call is stopped. This saves money and time.

The rule from the history: **every long-running operation must accept cancellation, and cancellation must propagate across the whole tree, including parents and unfinished nodes**.

## 5.5. The environment: commands that hang

The agent runs `npm install`, tests, and builds. Any of them can hang. In June 2024 a series of commits addressed this:

- `Implement timeout support for interrupting Bash commands` (27 June 2024). A timeout and the interruption of a command running in a persistent bash session.
- `set timeout to 25 sec, add suspend modifier` (28 June 2024). The first value was 25 seconds, and it was later increased.
- `Increase commands timeouts, add ctrl+z` (26 August 2024). Timeouts were raised, and `ctrl+z` was added for interruption.
- `Add command timeouts and error handling to ShellExecutor` (29 November 2024).

The current version of `ShellExecutor` (HEAD) moves the policy into a separate object:

```kotlin
data class CancellationPolicy(
  val commandExecutionTimeout: Duration,
  val commandCancellationTimeout: Duration,
  val commandSuspendingTimeout: Duration,
)

val defaultCancellationPolicy = CancellationPolicy(
  commandExecutionTimeout = 600.seconds,
  commandCancellationTimeout = 20.seconds,
  commandSuspendingTimeout = 20.seconds,
  // ...
)
```

Three timeouts, three meanings. Command execution is limited to 10 minutes. Cancelling a command (sending a signal) waits 20 seconds. Suspension waits 20 seconds. The separation matters: a cancellation has to be confirmed, and if the process does not respond, it must be killed rather than waited for forever.

The value of 25 seconds from June 2024 and the 600 seconds in HEAD differ by an order of magnitude. I did not find the reason for the change in the commits; the only visible fact is that the timeouts were revised several times. The useful conclusion: timeout values should be chosen for the real commands, not derived from theory.

A separate environment bug: a race in `NpmRunner` (31 May 2024, `Fix race condition in NpmRunner`). Two npm runs in the same project conflicted, and the result depended on their order. Serialization helps here too: one run at a time per project.

## 5.6. The budget: money as a resource

An agent that can call the model in a loop can also spend a lot of money. The cost limit appeared in May 2024:

- `Stop project generation process if the cost limit is reached` (23 May 2024). Generation stops when the cost exceeds the limit. The limit is set by the environment variable `MATTERHORN_COST_LIMIT`.
- `Add cost limit to the OpenAIProxy` (19 June 2024). The limit moved into the proxy, which sees every call. The exception `CostLimitExceeded` appeared.
- `Upgrade generation cost limit` (10 October 2024). The limit was raised. The value is not recorded in the history, and this is already a product decision rather than a code decision.

Inside the proxy, the cost was calculated from a price table that was hard-coded at the time:

```kotlin
val cost: Double get() = when (assistantKind) {
  Assistant_CHAT_GPT4o -> inputTokens / 1_000_000.0 * 5 + outputTokens / 1_000_000.0 * 15
  // ...
}
```

There is a trap here. Prices in code change together with models, and the table goes stale. In the current HEAD, `CostLimitExceeded` is defined in `core/src/.../ArtifactRequestExecutorService.kt` and used in `core/llm-grazie/.../GrazieLLMProxy.kt`: the cost check has moved into the layer that calls the model.

The rule: **the budget must be checked in one place that sees all model calls**, not separately in each worker. In Matterhorn the limit first applied to generation and only later to the proxy. The proxy sees every call, so the check there is more complete.

The cost limit is one more case where a restart is dangerous: when `CostLimitExceeded` is thrown, the project state may be half-modified. The next section is about that.

## 5.7. State: restart and rollback

The agent edits files. If it fails in the middle of an edit, the project is left in an intermediate state. The user wants two things: to restart the step and to roll back. For that, snapshots are needed.

The first step: `Save the initial project state and restore it when Rerun All Steps action is invoked` (31 May 2024). The initial project state is saved, and the "Rerun All" button restores it. A problem appeared immediately: an `IOException` when saving the state of FIFO files (4 June 2024). A snapshot of a file that is a pipe makes no sense. Judging by the fact that the fix dealt only with `IOException`, the decision was not to fail and to skip such files.

The second step: snapshots before and after an edit. The commit of 22 November 2024 saves not only paths but also contents:

```kotlin
class FileChange(
  val path: Path,
  val initialContent: String?,   // null — the file was created
  val newContent: String?,       // null — the file was deleted
)
```

This replaced the old structure, which stored only the paths of changed (`changedPaths`) and created (`createdPaths`) files. With the contents one can show a diff, roll back an edit, and understand exactly what a step changed. Note that `null` here encodes the absence of a file, and these are different states: "the file did not exist" and "the file is empty".

The third step: rerunning a single step with invalidation of its dependents. `Add rerun for a single step (invalidation)` (27 November 2024). Rerunning a step resets all the steps that depend on it. It is the same principle as the artifact tree from Chapter 1: when the input changes, everything downstream is recomputed.

The fourth: rerunning the generator's actions. `Fix rerun for Kineto actions` (9 December 2024). The Kineto line has been removed from HEAD (see Section 4.9), but the idea of rerunning made it into the agent's core.

## 5.8. Races and signals

Some errors do not reproduce on a single thread. From the history:

- `Fix concurrent modification exception for unfinished dependency update callback` (9 December 2024). A `ConcurrentModificationException` means a collection was modified and read at the same time. The commit message does not describe the details; the class of the error itself points to shared access from different threads.
- `Handle SIGINT in the backend app` (21 May 2024). On Ctrl+C the server must finish cleanly.
- `changed signal to SIGINT` (26 September 2024). The process stop signal was changed to SIGINT. The message is brief and gives no context. The practical conclusion: the same signal must mean the same thing in every part of the system.

## 5.9. The summary

The chapter in brief:

1. **Classify failures.** Transport, limit, environment, and logic failures require different responses.
2. **A retry needs a limit and a delay.** An infinite retry is not a policy.
3. **Every long operation accepts cancellation.** Cancellation propagates through the tree and is not mixed with errors.
4. **Timeouts are set for the real commands**, and their values change.
5. **The budget is checked where all calls are visible**, and the price table needs updating.
6. **Save the contents before an edit**, not just the path. Without it there is neither rollback nor diff.
7. **One signal, one meaning.**

## Exercises

1. Implement a wrapper around a model call: retry on 5xx with exponential delay, separate handling of 429 with a fixed delay and an attempt limit, and a clear message to the user when the limit is exhausted. Check that a 400 is not retried.
2. Add a shared budget for all model calls: a token counter and the price per model in one place. Stop the agent when the budget is exceeded, and verify that the partially modified project keeps a snapshot.
3. Run a command that hangs (for example, `sleep 1000`). Implement the three timeouts from Section 5.5: execution, cancellation, and suspension. Verify that the process is killed rather than left hanging.
4. Save the contents of a file before and after an edit. Show the diff and roll back the edit with one call.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates.
