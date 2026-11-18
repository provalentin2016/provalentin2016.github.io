# Chapter 7. The Execution Context: Who Holds What and When It Is Released

In Chapter 2 the agent became a loop; in Chapter 5 we talked about cancellation and budgets. But a loop raises a question that demonstration code usually does not ask: **who owns the resources that are open while the work runs?** A bash process, an HTTP connection, an MCP server session, a log file, an event subscription. If the agent finishes the task but the process stays alive, the user sees a "zombie" in the system. If a resource is closed while another step still uses it, you get an error in some random place.

In Matterhorn this task is handled by a pair of classes: `RootExecutionContext` and `ExecutionContext`. This chapter explains how they are built and why their rules are written down so carefully.

## 7.1. Two levels: the root and the node

The execution context is a tree. The root (`RootExecutionContext`) exists once per task or session. Nodes (`ExecutionContext`) are created for each request to an artifact and form the tree of calls.

The node's constructor shows the relationship:

```kotlin
class ExecutionContext(
  val root: RootExecutionContext,
  val parent: ExecutionContext?,
  val request: ArtifactRequest<*, *>,
  val data: ExecutionContextData?,
) : CustomArtifactEventLogger
```

Each node has a `root`, a `parent`, and the request it executes. Children are created through `createChildContext`. Statistics (time, tokens, cost) are computed at the node level and aggregated across the tree. In its current form these classes first appear in the commit that imported the code on 11 July 2024; their core concepts changed little afterwards.

The separation exists because the root and the node have different lifetimes. The root lives as long as the task and is responsible for resources. A node lives for one request and is responsible for accounting: how much time and money this step consumed. Mixing the two would mean either closing resources at every step or accumulating accounting forever.

To make sure the context reaches every coroutine the agent launches, a coroutine-context element is used:

```kotlin
class ExecutionContextElement(val uuid: UUID) : AbstractCoroutineContextElement(ExecutionContextKey)
```

The element is needed so that the context reaches the coroutines the agent starts, including the parallel tasks from Chapter 3.

## 7.2. Two ways to register a resource

The root stores "user data" (`userData`): resources and services bound to keys. There are two kinds of registration, and the difference between them is the central rule of the whole mechanism:

- `registerContext(key, value)` **borrows** the value. The root only looks it up by key. If the value implements `AutoCloseable`, that does not make it the root's property. Someone else will close it.
- `registerOwnedContext(key, value)` **transfers ownership**. The root closes the value on shutdown. The value must implement `CustomContext` and `AutoCloseable`.

The rules in the document `docs/root-execution-context-lifecycle.md` are strict: ownership transfers only on successful registration; an owned resource must not be closed by the caller; and it must not be handed to another root. An owned instance cannot be replaced through any key: that throws `IllegalStateException`.

Why two kinds? An example from the code: a service that exists once for the whole plugin (an LLM client, a cache) should be borrowed by tasks. A bash process opened for a specific task should be closed together with that task. If everything were "owned", the shared service would be closed when the first task ends. If everything were "borrowed", processes would leak.

The tests of `RootExecutionContextCloseTest` write these rules down as a specification. There are eighteen of them, and their names read like requirements: `close leaves borrowed closable contexts open across roots`, `borrowed registration cannot downgrade ownership`, `neither registration API can replace an owned instance`. For your own agent I would start with exactly such tests: they fix the behavior before any complex logic appears.

## 7.3. Closing: once, in registration order

The `close()` method is carefully built:

```kotlin
fun close() {
  val contexts = synchronized(userData) {
    if (closed) return
    closed = true
    ownedContexts.toList()
  }
  var cancellation: CancellationException? = null
  for (context in contexts) {
    try {
      context.close()
    } catch (e: CancellationException) {
      if (cancellation == null) cancellation = e
      else if (cancellation !== e) cancellation.addSuppressed(e)
    } catch (e: Exception) {
      logger.warn("Failed to close context ${context::class.java.simpleName}", e)
    }
  }
  listener.onContextClosed(this)
  cancellation?.let { throw it }
}
```

There are four decisions here, each worth remembering.

**Closing happens only once, under a lock.** The `closed` flag is set inside `synchronized`. A repeated call returns immediately. Even if the first close is still in progress, the second call does not wait for it and does not repeat the cleanup.

**Resources are closed one by one, in the order in which their ownership was first registered.** The order matters: if a resource registered later depends on one registered earlier, it must close first. Here the order is not reversed (as in a stack) but follows registration: the first registered is closed first. The document does not explain this, and for your own agent the order should be chosen explicitly and recorded.

**An ordinary exception is logged, and cleanup continues.** One failing resource must not prevent the others from being closed.

**A cancellation is rethrown at the end.** The first `CancellationException` is kept, and the others are attached as suppressed. Cleanup and the listener notification are carried out completely, and only then does the exception propagate. This is the same rule as in Chapter 5: cancellation is not an error, but it must not be swallowed.

A JVM error (`Error`) is handled differently: it interrupts the cleanup immediately, and there is no retry. The test `JVM errors escape cleanup and are not retried` pins this down. The logic is simple: an `OutOfMemoryError` or a `StackOverflowError` means the process state cannot be trusted, and continuing the cleanup is dangerous.

## 7.4. Races between registration and closing

The most delicate spot is registration that happens at the same time as closing. The document describes three guarantees:

- a registration after closing has begun throws `IllegalStateException`;
- a registration that races with closing either makes it in time and is included in the cleanup, or it does not make it and remains with the caller;
- a lookup after closing works, but the resource it returns may already be closed.

The last rule is not obvious. A lookup does not block, and the caller gets a reference that may become invalid at any millisecond. So resources used asynchronously must check their state themselves. The test `registration racing with close either transfers ownership or rejects it` checks exactly the first guarantee: there must be no third outcome in which a resource is lost.

Note that cleanup runs outside the registration lock. The test `concurrent close returns while cleanup runs outside the registration monitor` checks that a second `close()` call returns while the first is still closing resources. If cleanup ran under the lock, any resource that tried to register something while closing would create a deadlock.

## 7.5. A separate scenario: the plan watcher

In September 2026 the commit `JUNIE-5206 (PR B of 3): release PlanContext and coroutine children on task/root close` added a document describing a standalone agent scenario of its own. It is worth separate attention because it shows how the root and its child coroutines finish together.

The root of the standalone agent owns `PlanContext` and borrows the shared project services. The class `StandaloneAgentRunner` closes the root in a `finally` block, that is, whatever the outcome. `PlanContext.close()` requests cancellation of the watcher but does not wait for cleanup and does not cancel either the parent or the siblings. In the other direction, cancelling the parent stops the watcher.

The document describes this asymmetry as intentional. The plan watcher is a helper, and if it has not stopped instantly, that must not delay the task's completion. But if the task is cancelled, the watcher must stop as well.

## 7.6. What changed since 2024

The sequence of changes shows how the understanding of the context evolved:

- **11 July 2024** — the code was imported; the root and the node existed from the start.
- **17 September 2024** — the agent's context is stored in `ExecutionContext` as `userData`. The key `ExecutionContextUserDataKey` appeared: the agent no longer passes state through parameters but looks it up in the tree.
- **28 October 2024** — the commit "close context to avoid leak" closed contexts that had been leaking. The leaks were a direct consequence of ownership not being explicit.
- **29 August 2025** — the commit "Refactor to minimize usages of ExecutionContext (replace with Runtime)". Instead of one shared context, narrow interfaces appeared that extend `CustomContext`: `StopHookRuntime`, `PermissionRequestHookRuntime`, `ExternalHookRuntime`, and others. Each sees only what it needs.
- **23 September 2026** — ownership of `PlanContext` and its child coroutines became explicit, and a document and tests appeared.

Important: the move to narrow interfaces did not remove `ExecutionContext`. In `ej-core/src/main` it is still used in 212 files. The narrow `Runtime` interfaces are a slice, not a replacement. This is typical of refactoring large systems: a new abstraction is layered on top, and the old one stays until it is removed piece by piece.

## 7.7. What follows

1. **Record ownership explicitly.** If a resource can be borrowed or transferred, this must be visible in the API, not only in comments.
2. **Closing must be idempotent and safe under races.** A repeated call returns at once, and a registration after closing fails.
3. **A cancellation and an error during cleanup are different things.** Cleanup runs to completion; the cancellation is returned at the end.
4. **Record the rules as tests.** The test names in `RootExecutionContextCloseTest` work as a specification better than a document does.
5. **A tree is a good model for accounting.** Statistics are summed up the tree, while resources live at the level of the root.

## Exercises

1. Implement a root with two kinds of registration (a borrowed resource and an owned one). Write tests: a registration after closing fails, a repeated close does nothing, and an owned resource is closed exactly once.
2. Add a resource whose `close()` throws an ordinary exception, and check that the other resources are still closed and the listener is notified.
3. Add a resource that throws `CancellationException`. Check that the exception surfaces only after all the other resources have been cleaned up.
4. Run registration and closing in parallel a hundred times. Make sure no resource is lost: each is either closed by the root or remains with the caller.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The classes and tests were checked against HEAD. The document `docs/root-execution-context-lifecycle.md` is the main source of the rules; quotations from it are paraphrased.
