# Chapter 14. Context Management: What the Agent Remembers and What It Forgets

[← Previous](13-mcp-and-ide.md) · [Contents](README.md) · [Next →](15-sandbox.md)

A model has a context window: how many tokens it can accept in one request. An agent that works for a long time inevitably exceeds that window. The step history grows, tool results can be enormous, and pictures enter the conversation. Something has to be removed. The questions are what to remove, in what order, and how not to break the task.

The word "memory" is used in the project in three senses, and it is useful to separate them:

1. **The history of the current task** — steps, observations, tool results. It lives as long as the task is running.
2. **The agent's memory** — notes that outlive a task and carry into later sessions.
3. **Knowledge about the code** — an index and search over the repository, so that the agent does not have to read everything.

This chapter is mainly about the first sense, with brief excursions into the second and third. The story resembles what we saw in Chapters 2 and 5: first a simple rule, then a budget, then a reaction to an error.

## 14.1. Evolution: from five observations to a budget

In Chapter 2 we saw the first rule: the five most recent user messages are kept in full, and the rest are collapsed. That was reasonable for the SWE-style agent, whose steps are short.

Then a set of strategies appeared. As early as July 2024, settings for the history of agents appeared (the commit "add LLM and HistoryProcessor configs for agents"). The enumeration `HistoryProcessors` in its current form, with four values, has existed since 2 October 2025:

- `None` — the history is not shortened;
- `Last5Observations` — the rule from Chapter 2;
- `Compress` — compression through a separate model call;
- `UnlimitedStepsProcessing` — compression by a token budget.

The choice of strategy is a setting of the agent, not a constant in the code. This makes it possible to compare strategies on the same task, which is what the evals do (Chapter 10).

In October 2025 the `UnlimitedStepsHistoryProcessor` appeared (the commit "add UnlimitedStepsHistoryProcessor", 2 October). It became the main strategy for long tasks, and the logic and constants around it are now built on a budget.

## 14.2. The token budget and its estimation

To compress against a budget, you need to know how many tokens a text occupies. There is no exact way to know before the request is sent, so the code estimates. The constants in `UnlimitedStepsHistoryProcessor` show how:

```kotlin
private const val CHARS_PER_TOKEN: Int = 3
private const val KEEP_TAIL: Int = 10
private const val MAX_KEPT_TOOL_RESULT_CHARS: Int = 2_000
private const val TRUNCATED_TOOL_RESULT_HEAD_CHARS: Int = 1_000
private const val CALIBRATION_WINDOW: Int = 5
private const val MIN_CHARS_PER_TOKEN: Double = 1.5
```

The initial estimate is three characters per token. It is crude, but adequate for most texts. Then calibration comes into play: over a window of the five most recent steps, the estimate is compared with the actual number of tokens the provider returned. The estimate cannot drop below 1.5 characters per token, even if calibration suggests otherwise — a protection against outliers.

Note that calibration works because the provider reports the actual usage. If the estimate relied only on a constant, it would drift away from reality with every new language or toolset.

The target budget depends on the size of the window: a safety factor of 0.9 for windows up to 300,000 tokens and 0.95 for larger ones. The margin is needed because the estimate is always slightly off, and the last step must not drown in an overflow.

## 14.3. What is compressed first

The order of compression is the main choice of the strategy. The code follows a simple idea: **fresh matters more than old, large matters more than small**.

- **Observations older than ten steps** (`KEEP_TAIL = 10`) are replaced with textual summaries. The last ten remain in full.
- **Tool results longer than 2,000 characters** are cut down to a head of 1,000 characters. The tail, which usually matters less, is discarded.
- **Pictures**: the last three remain, and the older ones are replaced with a placeholder. The placeholder's text is honest: "Image content omitted to save context; a textual summary was not available yet". The model knows that the information is lost and does not make it up.
- **Progressive truncation**: if one reduction is not enough, the code tries keeping tails of 10, 5, 2, and then 1 observation. The tighter the budget, the shorter the tail.

The difference from Chapter 2 is visible here: back then we collapsed whole messages. Now it is not the message but a part of it that gets collapsed, and the choice depends on size. A small observation is better left as it is, even if it is old, because compressing it would gain nothing.

The honesty of placeholders is a general lesson. When the model cannot see some information, it must be told so explicitly. Otherwise it will answer confidently on the basis of an empty space.

## 14.4. Reacting to overflow

An estimate can be wrong, and the request will still be rejected: `LLMContextLengthExceeded`. This is where reactive compression comes in. The commit "shrink the history and retry a step that overflowed the context" (4 November 2026) added a retry: a step that did not fit is replanned with a compressed history. There are two attempts (`MAX_CONTEXT_OVERFLOW_RETRIES = 2`). After that, the error propagates upward.

The chain looks like this:

```
estimate → budget → compression before the step
              ↓ (if the estimate was wrong)
   request rejected: LLMContextLengthExceeded
              ↓
   state compression → retry of the step (at most 2 times)
              ↓ (if that did not help)
   error propagates upward
```

Two levels of protection are needed for different reasons. Proactive compression saves money and time: a request that will certainly not fit is never sent. Reactive compression is insurance for the case when the estimate was wrong. Without the second level, a single wrong estimate brings down the whole task.

The limit of two retries matters too. If compression does not help after two attempts, the problem is not the history, and an infinite retry would only burn money.

The history of this mechanism has two layers. Handling of the error "context exceeded" has existed since February 2025. But the retry of a step with compression and the proactive compression before a step appeared in a single commit of November 2026 ("unify context budget pruning and naming"). So the system could at first only report the error, and it learned to recover only recently.

## 14.5. The agent's memory: notes between sessions

A separate mechanism is the agent's memory, which outlives a task. It appeared in October 2025 ("[MEMORY] - memory init", 31 October). The memory is a text document that grows from session to session. Without a limit it would fill the whole window within a few weeks.

For this there is `MemoryCompactor`. Its logic is short: if the memory text does not exceed the threshold `COMPACTOR_THRESHOLD`, it is returned as is. Otherwise it is compressed, and the method `truncateByBlocks` discards blocks. The name is telling: the compression works not by characters but by semantic blocks, so that no entry is cut in half.

Cutting by blocks is a good rule for any structured text. Truncation by characters leaves half a sentence, and such a half is worse than nothing: the model takes it for a fact.

## 14.6. Knowledge about the code: index and search

The third sense of memory is knowledge about the repository. Reading every file into the context is impossible, so search is needed. The project has two related directions.

The first is the indexing and search of **EmbArk** (the commit "support EmbArk indexing and search", 28 August 2025). In November 2025, parsers for Kotlin, Java, and Python were added: an indexer has to understand the structure of a language in order to find definitions rather than strings. For the concrete implementation of semantic search (embeddings), this chapter will not claim more than the history shows.

The second is the integration of an external semantic search into the CLI (`JbContext`, August 2026). It installs a binary tool, indexes the repository, and gives the agent search. The code contains a protection worth noticing:

```kotlin
// A repository without an index searches nothing while the CLI still exits 0,
// so stop before the agent runs.
internal fun requireIndexedRepository(status: List<String>) { ... }
```

The problem here is a typical one: a tool that found nothing because there is no index returns a success code. The agent sees an empty result and concludes "there is no such thing in the code", although the search simply did not work. The protection stops the launch before the agent starts working. The lesson: **an empty result and the absence of a result must be told apart**, and checking the availability of a tool must be a separate step.

## 14.7. What changed over two years

A summary:

- **July 2024** — the enumeration of history strategies.
- **February 2025** — handling of the context-overflow error.
- **August 2025** — indexing and search over the code.
- **October 2025** — `UnlimitedStepsHistoryProcessor`, the enumeration of strategies, the agent's memory.
- **November 2025** — index parsers for three languages.
- **July 2026** — `CHARS_PER_TOKEN` and support for `maxContextLength` in the model configuration.
- **August 2026** — integration of semantic search into the CLI.
- **November 2026** — calibration of the token estimate, retry of a step with compression on overflow, and proactive compression before a step.

It is clear that in 2026 the main question shifted: not "how to compress", but "how not to be wrong in the estimate, and how to recover". Calibration and retry on overflow are the answer to this question.

## 14.8. What follows

1. **Distinguish three kinds of memory**: the task's history, the agent's memory, and knowledge about the code. They are compressed differently.
2. **Compress against a budget, not by the number of messages.** A constant of five messages does not account for their size.
3. **Calibrate the estimate against actual usage**, as reported by the provider.
4. **Protect yourself twice**: proactively, do not send a request that is certain to be too large; reactively, recover when it is rejected.
5. **Placeholders must be honest**: the model must know that information has been lost.
6. **Cut along semantic blocks**, not characters.
7. **An empty search result and a failed search are different things.** Check that the tool is available before the agent starts.

## Exercises

1. Implement a step history with a token estimate of three characters per token. Add calibration over a window of the five most recent steps, using the actual token counts from the model's responses. Verify that the estimate converges within a few steps.
2. Implement compression: observations older than 10 steps are replaced with summaries, and tool results longer than 2,000 characters are cut down to their first 1,000. Verify that the last 10 steps do not change.
3. Simulate a model rejection due to overflow (you can trigger it artificially with a small limit). Implement a retry of the step with a compressed history, at most two times. Verify that a third rejection propagates upward.
4. Write a search tool that returns an empty list if the index has not been built. Then add a check for the index's availability, and verify that the agent does not start without an index and prints a clear message.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The constants and classes were checked against HEAD: `UnlimitedStepsHistoryProcessor.kt`, `AbstractIssueAgentWorker.kt`, `MemoryCompactor.kt`, `JbContext.kt`. About the concrete semantic-search implementation in EmbArk, the text says only what is visible in the history.
