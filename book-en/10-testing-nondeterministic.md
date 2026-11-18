# Chapter 10. Testing a Non-Deterministic Agent

An ordinary test checks that a function produces one output for one input. With an agent this does not work. The same task can yield different solutions, different sequences of actions, and different wording. Every run costs money and takes minutes. Testing "by eye" is impossible, and running a full pass on every change is expensive.

Matterhorn solved this in layers. Below are five levels, from cheap to expensive, and the most interesting of them is the cache of model requests, which turns non-deterministic calls into reproducible ones. The chapter describes them in order.

## 10.1. Levels of verification

The pyramid looks roughly like this:

| Level | What it checks | Cost | Where it runs |
|---|---|---|---|
| Unit tests | logic without the model | close to zero | every commit |
| Tests with a recorded model response | the agent's behavior on known answers | low | every commit |
| Cache check in CI | that outgoing model requests have not changed | low | every PR |
| E2E tests of the built binary | the interface and the startup of the CLI | medium | builds |
| Evals (assessment on tasks) | the quality of solutions | high | on demand |

The lower levels catch regressions cheaply; the upper levels assess quality at a high price. It matters not to confuse their roles: a green unit test does not mean the agent has become better, and a failed eval does not always mean the code is broken.

## 10.2. The request cache: record once, replay always

The core idea: store the model's answer to every request, and when the same request comes again, return the stored answer. Then a run becomes deterministic. The model is called only on the first run or when the request changes.

The cache is implemented in `core/llm/.../AICaches.kt` in two variants: a local one (`LocalAICaches`, files in the Junie directory) and a Redis one (`RedisAICaches`, shared by CI). The first version of the Redis cache appeared on 27 August 2024.

The cache key is a hash of the **normalized** request. The normalization is described in `AICacheKey.kt`:

```kotlin
internal fun String.fixUnstableTextForCaches(): String {
  // run times, trace identifiers, temporary build paths,
  // object addresses in memory, version hashes — everything that changes between runs
  ...
}

fun fromText(text: String): AICacheKey {
  val fixed = text.fixUnstableTextForCaches()
  return AICacheKey(initialKey = text, stableKey = fixed, stableKeyHash = fixed.hash256())
}
```

There are two keys here. `initialKey` is the original text of the request; it is needed for debugging, because from it you can see exactly what was sent. `stableKey` is the text after the unstable parts are removed; its hash is the key. Storing both makes the cache understandable: on a miss you can see which request was not found.

Normalization is the most dangerous part of the scheme. If it is too weak, random details get into the key, and the cache misses on every run. If it is too strong, it hides real changes, and the cache returns an old answer for a new request. The balance is encoded in a list of regular expressions. The test `scratch normalization leaves unrelated paths unchanged` checks that normalization does not touch unrelated paths: it could accidentally erase useful parts.

Why the request, not the task's input? Because the model's answer depends on everything that goes into the request: the prompt, the tool descriptions, the conversation history. Any change in these parts changes the key. This is a property, not a defect: the cache itself shows that the request has changed.

## 10.3. Recording misses

A cache is useful only if you can see when it misses. For this, misses are written to two files, which appeared in October 2024 together with a refactoring "introduce a single place for saving and loading cache entries":

- `NonCachedRequests` — the hash of every request that was not in the cache;
- `LLMRequestsFull` — the full stable text of such a request.

The first file gives a list of misses; the second shows what exactly changed. Without the second, investigating a miss would have to be done by hand.

## 10.4. Redis: who wrote first

In Redis the write uses the command `setnx` — "write if the key does not exist yet":

```kotlin
val keyWasSet = commands.setnx(key.stableKeyHash, json.encodeToString(response))
if (!keyWasSet && canReadFromRedis)
  commands.get(key.stableKeyHash)?.let { return json.decodeFromString<AIAnswer>(it).asCached() }
```

If two parallel agents request the same thing at the same moment, the first writes its answer, and the second sees that the key already exists and reads the stored answer. Both receive one result. Without `setnx`, the second would overwrite the first, and during a long replay the answers would diverge.

The flags `MATTERHORN_CAN_READ_FROM_REDIS` and `MATTERHORN_CAN_WRITE_TO_REDIS` separate reading from writing. This matters for CI: a build may read the shared cache but must not change it. Only the owner of the shared cache may write to it.

## 10.5. CI: a change of requests is a change of behavior

The repository's README states that a merge is forbidden if one of the checks fails: "Check Redis Cache", "Check Agent Execution", "Check Redis Cache (Standalone)", or "Build & Check". The check "Check Redis Cache (Standalone)" does something special: it **replays** a set of reference tasks against the recorded answers and verifies that the outgoing model requests have not changed.

If a request has changed, the build fails with the message `Failure (Redis cache misses)`. The artifacts contain `cache_misses.json` and `detailed_cache_misses.json`. The rule from the skill for investigating builds is as follows:

1. Look at the first miss in each instance: the others are usually consequences of the first.
2. If the change should not have affected requests, fix the code so that the request matches again.
3. If the change is intended, explain it to the engineer who owns the model, and they will update the cache. Updating the shared cache yourself is not allowed.

An important idea is hidden here. **The prompt, the tool description, and the order of the history are a contract with the model, and changing them must be visible in review.** Usually a prompt change looks like a text edit and passes unnoticed. The cache turns it into an event that requires an explanation. The price: every prompt edit requires an extra step.

Note that the check does not say whether the agent has become better. It only says the requests have not changed. Quality is verified at other levels.

## 10.6. E2E: the built binary as a user

The cache checks logic, but not how the program starts. For that there is the module `cli-e2e-tests`. It launches the built Junie CLI binary inside Docker through a pseudo-terminal (PTY) and describes the interaction through **screens**: the test sees what the user sees and sends input the way the user does.

The module appeared in March 2026 and works in three modes. E2E tests in Docker check the installed builds (Release, EAP, Nightly). Snapshotter tests run locally, without Docker, and write readable logs of screen snapshots, for quick iteration. The Snapshotter server exposes the same terminal over HTTP: an external agent can send input (`POST /input`), retrieve a snapshot (`GET /snapshot`), and stop the session. The last mode is an example of tools for testing agents becoming agents themselves.

## 10.7. Evals: assessing quality on tasks

The quality of solutions is checked by evals. The module `ej-app/cli-evals` appeared in October 2025. It runs the CLI as an external process and collects the result. Its code shows which problems the assessment has to solve:

- **A hard time limit.** A comment in `CliAgentExecutor` says that when the limit is exceeded "the process tree is killed". The whole process tree is killed, not just the parent. An agent that started a build would leave it running if only the main process were killed.
- **Line-by-line logs with timestamps.** The class `TimestampedLine` keeps the original line and the time it was captured as separate fields. A comment explains the reason: do not modify the original line, for example by inserting a timestamp into JSON. Otherwise later parsing breaks.
- **Incremental writing.** Each line of output is passed to the handler immediately, so the logs survive even an abnormal termination.

Evals are expensive. For a skill that runs the agent's external CI tests, the document states plainly: a regression run takes 20 to 50 minutes and costs about six dollars, and a run per goal costs about one dollar. Such tests are run only on explicit request. This is a good example of testing cost having to be counted just like the agent's own cost.

## 10.8. Chronology: from the cache to evaluations

This is how the testing infrastructure developed:

- **27 August 2024** — the request cache in Redis. The first version that allowed the agent to be tested without repeated model calls.
- **14 October 2024** — a single place for saving and loading the cache, with recording of misses.
- **24 October 2025** — `cli-evals`, assessments of the CLI as an external process.
- **3 February 2026** — CI instructions added to the README, including the list of required checks.
- **11 February 2026** — the cache key is built from the final text of the request (the commit "Apply AI Caches for the final text of AI Request").
- **18 March 2026** — the E2E module and the Snapshotter.

The order is telling: first the team learned not to spend money on repetitions (the cache), then to catch changes in requests (CI), then to test the interface (E2E) and quality (evals).

## 10.9. What follows

1. **Reproducibility is the cache.** A recorded model response turns a non-deterministic call into a deterministic test.
2. **The cache key is the boundary between "the same" and "different".** Normalization must be explicit and covered by tests.
3. **The prompt is a contract.** Changing it must be visible in review and explained.
4. **Log the misses.** Without the full text of the request, a miss is useless for diagnosis.
5. **One owner writes the shared cache.** Everyone else only reads.
6. **An external process must be strictly limited.** A time limit and killing the process tree are mandatory.
7. **The cost of tests is part of the design.** Expensive checks run on demand; cheap ones always.

## Exercises

1. Implement a cache: the key is a hash of the request, and the value is the model's answer. Store both `initialKey` and the normalized `stableKey`. Check that two requests differing only in a timestamp produce the same key.
2. Write a normalization that removes temporary build paths. Add a test: a path with an ordinary name is unchanged, and a path inside a temporary directory is collapsed.
3. Add a check "the outgoing requests have not changed": replay three reference tasks against the recorded cache and fail if a miss appears. Then change the prompt on purpose and verify that the check fails and shows the first miss.
4. Write an evaluation: run the CLI agent as a process with a 60-second time limit. When the limit is exceeded, kill the whole process tree. Verify that a child process started by the agent is stopped too.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The classes and tests were checked against HEAD. The CI rules come from the README and the repository's skills. The addresses of the internal CI server are not given in the book.
