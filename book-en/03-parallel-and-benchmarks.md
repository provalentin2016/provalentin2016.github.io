# Chapter 3. Parallelism and Benchmarks

[← Previous](02-agent-loop.md) · [Contents](README.md) · [Next →](04-recipes-knowledge.md)

An agent that works on one thread and performs one task teaches almost nothing. To know how good it is, you have to run it many times on different tasks. To do that in reasonable time, you need parallelism. And in an agent, parallelism both speeds things up and breaks everything that assumes sequential order: logs, the interface, the shared state of the project.

This chapter is about how Matterhorn arrived at parallel runs. It all began with a benchmark, not with a product.

## 3.1. The first benchmark: HumanEval

The earliest experiment visible in the history is solving HumanEval tasks. (The repository has earlier commits, for example from 19 March 2024, but they are not about experiments.) HumanEval is a standard set of tasks: write Python functions from a description and a set of tests. For an agent it is convenient: the task is short, the result is checked automatically, and the reference is known.

The first commit is `Initial HumanEval solving` (22 March 2024). A week later came:

- `running tests until HumanEval problem is solved` (2 April 2024). The agent runs the tests in a loop and edits the code until they pass. This is the seed of what later became the check inside the agent's loop.
- `Refactoring HumanEval workers` (10 April 2024).
- `Enable running HumanEval in command-line mode` (15 April 2024). The experiment could now run without the IDE. This was the decisive step: without a CLI, experiments cannot run in CI.
- `Run HumanEval problems in parallel` (16 April 2024).

An important point for the book: the history contains no commit with the final share of solved tasks. We cannot say how many tasks the agent solved in April 2024 or how much the versions differed. Results, if they existed, lived in CI logs or in tables that are not in the repository. So this book does not give accuracy figures; it describes only the infrastructure.

## 3.2. Parallel task processing

The way the parallel run works is visible in the commit of 16 April 2024. Previously the tasks ran in a loop with error handling:

```kotlin
for (problem in input.problems) {
  try {
    // generate a solution for one task
  } catch (e: Exception) {
    // Ignore the problem
  }
}
```

It became this: each task is a separate coroutine, and errors are counted:

```kotlin
var failedProblem = AtomicInteger(0)

coroutineScope {
  input.problems.map {
    val problem = it
    async {
      try {
        // generate a solution for one task
      } catch (e: CancellationException) {
        throw e                          // do not swallow cancellation
      } catch (e: Exception) {
        failedProblem.incrementAndGet()  // count it, do not ignore it
      }
    }
  }.awaitAll()
}
```

Three details here matter, and each recurs elsewhere in the history.

**Cancellation must not be swallowed.** `CancellationException` is rethrown upward. Otherwise the "Stop" button cannot stop the parallel tasks. The same mistake surfaced in the commits about cancellation (Chapter 5).

**Errors are counted.** In the original code the error of one task silently disappeared. After the change it can be seen in the statistics. For a benchmark this is essential: a silently failed task looks like one that never tried.

**Order is not guaranteed.** `awaitAll` waits for everyone, but the results arrive in arbitrary order. Anything that depends on order, such as logs written to a file, has to be rewritten.

## 3.3. Multithreading in the IDE

Problems began when parallel tasks started writing to a single place: the IDE chat, the artifact tree, a shared state object.

The commit of 29 March 2024 is one of the most revealing. Its message: "Switch to request batch processing instead of streaming to avoid UI freezing. When several threads are writing their results to the chat, it leads to UI freezing". In other words, streaming results into the chat from several threads froze the interface. The fix: accumulate the responses and send them in batches.

The lesson is simple and general: **the interface is also a shared resource, and writing to it in parallel requires the same discipline as writing to a database**. Batch sending is slower in theory but faster in practice, because the interface does not repaint on every token.

The next step was `Fix multithreading issues` (16 April 2024). One commit rewrote `ExecutionContext` and `RootExecutionContext`: instead of manual thread management, a `parallelProcess` function appeared, which runs tasks through `async` and `awaitAll` and accounts for execution time. The commit also removed the old `EDT` and `readText` calls, which had been creating blocking between threads.

The error "Access from Event Dispatch Thread (EDT) is not allowed" surfaced several times. The commit of 5 September 2024 is a separate fix for this error. The general rule from the history: anything that touches the UI or the VFS goes through an explicit switch to the right thread, rather than relying on the call happening to work.

## 3.4. Logs you cannot mix up

A parallel run produces logs that cannot be read. Ten tasks write "testStarted", "testFinished", and "testFailed" into one output, and after a minute you know only that something failed.

Matterhorn used the service-message format of TeamCity. These are text lines like `testStarted name='...'` that CI can parse and show as a test tree. For a single thread the format works. For a parallel run it does not: messages from different tasks interleave, and CI cannot tell which test a message belongs to.

The solution is a flow identifier (flowId). The commit of 16 April 2024 added it to every message (an abbreviated example of the format):

```
testStarted name='solve_problem_12' flowId='...'
testFinished name='solve_problem_12' flowId='...' duration='4312'
```

Messages of one test are now linked by one identifier, even when messages of other tests arrive in between. Escaping came next: the commit of 5 June 2024 applied the same rules to the flowId as to the test name. The commit of 4 June 2024 replaced spaces with underscores in `TeamCityLogger`. The commit message does not give the reason; in substance it is the same class of problem: spaces broke the parsing of attributes.

Separately, the commit of 20 May 2024 applied `toTeamCityFormat()` to test names. Without it, any character that TeamCity treats as special broke the parsing of the whole block.

The conclusion: **when there are many agents, every event must carry an identifier of whoever it belongs to**. In a more mature form this principle returns in Chapter 19, where the events of Junie Live are tied to instances.

## 3.5. CI as a laboratory

In the project's history, TeamCity was not only a tool for tests. It became the execution environment of the agent:

- `Use "." working directory on TeamCity` (15 July 2024). The agent on CI must work in the root of the checkout, not in the IDE's directory.
- `Always generate images using OpenAI on TeamCity` (28 August 2024). The CI configuration differs from the local one: on CI the image provider is fixed. The message does not explain why; in substance it serves reproducibility.
- `Temporarily replace recipe for TeamCity` (4 September 2024). The recipe on CI was temporarily swapped. The message does not say why.
- `Report to teamcity if backend or frontend generation is failed` (29 August 2024). A generation error is now visible in CI as a failed test, not merely as a line in the log.

An interesting combination appears here: CI both checks the agent (the tests of the code it wrote) and serves as its test bench (a benchmark). These are two different modes, and the history mixes them.

## 3.6. Parallel edits of one project

The hardest case is when several parallel agents change the same project. The commit of 31 July 2024, `Run tests in parallel and merge changes`, worked like this: each attempt operates on a copy of the sources (`source.copy()`), and its result is merged back into the main project. If the merge fails, a fallback path kicks in: a separate agent step, `Apply changes`, receives the text of the edits that did not apply and asks the model to reproduce the same result again. In other words, when a merge fails, another attempt by the agent resolves it, not a human. This is convenient, but it makes a merge error expensive: it costs one more model call.

Later came `Refactoring of EditWorkers` (September 2024) and `EditWorker: Fixed issue with same artifactId for different critique attempts` (26 September 2024). The last one is telling: two parallel variants of an edit received the same artifact identifier, and one overwrote the other. Such errors cannot be caught on a single thread.

The recommendation from the history: **the artifact identifier must include the attempt, not only the object being worked on**.

## 3.7. What follows

1. The benchmark is needed before the product. Matterhorn began with HumanEval, presumably because without automatic checking it is impossible to tell whether anything has improved.
2. Parallelism requires three things: do not swallow cancellation, count errors, and tie events to their source.
3. The interface is a shared resource just like a database, and it needs the same discipline.
4. CI can be used as a laboratory, but then its configuration becomes part of the experiment.

## 3.8. What became of it in the current code

The infrastructure has proven more durable than specific tasks. `TeamCityLogger` and `ArtifactRequestExecutorService` remain in `core/src/main/kotlin/.../helpers/` and `.../ArtifactRequestExecutorService.kt`, so the TeamCity service-message mechanism and the executor of model requests are alive. The HumanEval benchmark classes were removed: they are not in HEAD. The rule "do not swallow cancellation" has survived: in `core/` about sixteen places catch `CancellationException`, and in the examples checked (`AICaches.kt`, line 185) the exception is rethrown. This rule is worth checking in every refactoring of parallel code.

## Exercises

1. Take a set of 20 simple tasks (for example HumanEval, or your own). Write a loop that solves them sequentially and measure the time. Then switch the loop to a parallel run through `async`/`awaitAll` with a limit on concurrent tasks. Compare the time and the number of errors.
2. Add a run identifier to the log of each task. Check that, when lines are written in parallel to one file, you can separate them by task.
3. Break the cancellation handling on purpose (swallow `CancellationException`) and verify that the stop button stops working. This is the best way to remember the rule.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates.
