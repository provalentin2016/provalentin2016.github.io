# Chapter 8. Tools and Edits: How the Agent Changes the World

[← Previous](07-execution-context.md) · [Contents](README.md) · [Next →](09-subagents.md)

An agent that only thinks is harmless. Harm and benefit come from actions: writing a file, running a command, making a network request. This chapter is about how such actions are described, how they are executed, and how they are checked before they change anything.

Almost everything described here has survived several rewrites. So the order is: first the model of actions, then file edits, then user confirmation. At the end, an error that shows why classifying commands by their text is fragile.

## 8.1. The action as a contract

In Chapter 2 the agent had four actions, each described by a name, a text for the model, and two functions. The contract is more elaborate now. The interface `ToolAgentAction` adds a parameter schema, which the model receives:

```kotlin
interface ToolAgentAction : AgentAction {
  val toolParametersSchema: ToolParametersSchema
  val inputExamples: List<JsonObject>?
    get() = null
}
```

The schema is turned into a JSON Schema for the provider. For text actions there is a base class, `BaseToolTextAgentAction`: it builds the schema itself from a list of parameters, each with a type (`INTEGER`, `STRING`, and others), a description, and a flag for whether it is optional. The developer of an action describes the parameters declaratively, and the schema is derived from that description. This reduces the mismatch between what the code expects and what the model sees.

Note `inputExamples`: optional examples of input data. It is the same technique as the format examples in Chapter 2, only now in a structured form.

Every action belongs to a group (`actionGroup`). Behavior is derived from groups: for example `EDIT` and `CREATE` change files, `SUBAGENT` spawns a nested agent. The group is not cosmetic: the order of execution depends on it, as we will see below.

There are also terminal actions: `SubmitAgentAction`, `AnswerAgentAction`, `suggest_plan`. They end the loop (Chapter 2). Their names are collected into a dedicated set, `TERMINAL_ACTIONS`, and the loop checks membership in that set instead of comparing individual strings in the code.

## 8.2. Editing a file: three generations

The history of editing is the clearest part of this chapter. Each generation solved a problem left by the previous one.

**Generation 1: search and replace.** The tool `search_replace` appeared in August 2024, as part of a subagent editor. The model passes a fragment to find and the replacement text. The tool's instructions contain a strict rule: a fragment that occurs more than once in the file is rejected with an error, unless the flag for replacing all occurrences is set:

> A *SEARCH* pattern that produces multiple matches in the source code will be rejected as an error, unless `replace_all` is set to true.

The rule is simple but important. If the model asks for a replacement without unique context, the edit may land in the wrong place. So refusing is safer than guessing. The model receives an error and must extend the fragment until it becomes unique.

**Generation 2: patches.** The tool `apply_patch` appeared in May 2025, first for the IDE frontend (passing a pointer to an interface element for incremental changes), and in October 2025 it received an independent implementation, `StandaloneApplyPatchAction`. A patch is a diff format that the model produces as a whole. For multi-file edits it is more convenient, but it demands an exact format: a single extra space in the context makes the patch unapplicable.

**Generation 3: multi-edit.** The tool `multi_edit` appeared on 18 October 2025. It is built on top of `search_replace` and applies several replacements to one file in a single call. Its instructions state outright that it is preferable to a single replacement when there are several edits, and that `replace_all` is preferable when the same line changes in many places.

The conclusion: **editing tools are a compromise between precision and expressiveness**. Search-and-replace requires uniqueness, a patch requires an exact format, and multi-edit saves calls but makes errors harder: if one of the edits in the batch does not apply, what happens to the rest? The tool's instructions settle this: "The edits are atomic - either all succeed or none are applied". A partial application would leave the file in an unclear state.

## 8.3. Checking after an edit

An edit without a check is a hypothesis. That is why, after a change, `ErrorCheckingService` runs. It appeared in August 2025 ("Move error checks to services and localize their printing"). It checks the documents touched by the edit for compilation and analysis errors and returns the result to the model in the same response. The check runs at a configured level of detail (`ErrorCheckLevel`) and with a timeout, so it cannot block the agent forever.

It is useful to separate two questions: "did the edit apply?" and "is the edit correct?". The first is answered immediately; the second by a check. An agent that conflates them either reports success after silently corrupting a file, or wastes steps reverting edits that were successful.

## 8.4. The change as an object

Edits must be observable: the user wants to see a diff, to roll back, to understand what changed. For this, each change is represented by the class `FileChange`:

```kotlin
data class FileChange(
  val beforeContent: FileChangeContent?,
  val afterContent: FileChangeContent?,
  val beforeAbsolutePath: Path,
  val beforeRelativePath: Path,
  val afterAbsolutePath: Path = beforeAbsolutePath,
  val afterRelativePath: Path = beforeRelativePath,
)
```

Three decisions here matter.

**`null` encodes existence.** `beforeContent == null` means the file did not exist (a creation); `afterContent == null` means the file was deleted. An empty file and a missing file are different states, and the code distinguishes them explicitly. This is the same rule as `initialContent` in Chapter 5.

**There are two paths: before and after.** A rename is expressed as a pair of paths, not as a separate operation. So the diff and the rollback work the same way for every kind of change.

**Content can be text or binary.** `FileChangeContent` is a sealed type with two implementations: `TextFileChangeContent` and `BinaryFileChangeContent`. A diff of a binary file is meaningless, and the code does not attempt to build one.

On top of `FileChange`, the edit history `EditsHistory` works. In April 2026 the command `/revert` appeared, which rolls back the agent's edits. Without storing "before" and "after", such a command would be impossible: a rollback requires the exact content of the file before the edit.

## 8.5. Confirmation: whom to trust

Not every action needs confirmation. Reading a file is safe; deleting a database is not. So confirmation is placed in a separate layer, `HumanInLoop`, with three modes:

```kotlin
sealed interface HumanInLoopSettings : CustomContext {
  class Interactive(...) : HumanInLoopSettings
  object AllowAll : HumanInLoopSettings
  object AskAll : HumanInLoopSettings
}
```

`AllowAll` and `AskAll` are the extreme cases. `Interactive` is the main one: it relies on a list of allowed actions (`AgentActionsWhitelist`), a "brave" mode (allow everything without asking), and predicates: whether a file is sensitive, whether it must be ignored, whether it belongs to build scripts. These predicates are passed as functions rather than as lists of paths, because the decision depends on context.

The allowlist appeared in April 2025 as "customizable brave mode whitelist". A "readonly commands" mode is switched on separately: read-only commands such as `ls` or `cat` run without asking. Here the most instructive part begins.

## 8.6. A classification error: when a read-only command writes

The classifier of read-only commands parses the command line and decides whether it is safe. In November 2026 the commit "Harden readonly command classification against redirection bypasses" closed a series of bypasses. The commit messages describe them concretely:

- `uniq -- in -out` and `xxd -- f -out` wrote a file while being classified as read-only. The cause: the flag `-out`, placed after `--`, was treated as an option rather than an operand.
- `echo hi >/x/ls` and `env>>f`: a redirection sat inside the token of the executable. After the name was normalized, it turned into `ls` or `env`, that is, into an allowed command. The allowlist of commands therefore permitted writes outside the project.
- `rg --hostname-bin`, `yq --split-exp-file`: options that run other programs or write files.

Each case is not a random mistake but a class of mistakes: a classifier that understands the line as text rather than as a shell command will always lag behind. The `xxd` tool parses its own arguments, and its rules differ from the general rule "a flag starts with a dash". For the check to be reliable, the parsing must match what the program itself does.

The lesson for your own agent: **do not try to classify commands by syntax for each program by hand, if you can avoid it**. Better options: run read-only commands in a sandbox (the project's history has a separate sandbox module for this, which we will discuss in Chapter 15), or limit the allowed commands to a small set without arguments that could write.

## 8.7. The order of execution

When the model returns several actions in one response, they are executed in one of two ways. The rule that chooses the way is written in `AgentActionsExecutor`:

- If the response contains subagents, the parallel path is taken: the subagents work independently, while edits within that path still run in order.
- If the actions are read-only, they run in parallel.
- If there are edits among them (`EDIT` and `CREATE`), the edits run **sequentially** inside one asynchronous block, while the read-only actions run in parallel alongside.
- The results are returned in the order of the original requests, not in the order of completion.

The last rule matters: the model expects answers in the same order in which it sent the requests. If the results were shuffled, the model would link a read to the wrong request.

There is also a separate branch for models that work better with sequential execution. The commit "consecutive tool execution for gemini models" (October 2026) added a mode in which actions run one at a time, if the model is from xAI or Gemini and the response contains no subagents. The code comment says directly that these models often call several tools and expect sequential execution. This is an example of model behavior differing, and the executor must take it into account.

Separately, the commit "[EDITS] - Parallel edits fix" (November 2026) resulted in the edits of one response being applied one after another. The commit message is brief and does not describe a specific conflict; the code shows that parallel edits are no longer run at the same time.

## 8.8. What follows

1. **An action is a contract.** Name, parameter schema, group, examples. Derive the schema from a declaration rather than writing it by hand.
2. **Refusing is safer than guessing.** A search-and-replace with a non-unique fragment should fail, not pick one occurrence.
3. **An edit is an object.** Keep "before" and "after", and the diff, the rollback, and the check all become possible.
4. **Check the result of an edit**, not only the fact that it was applied.
5. **Confirmation is a separate layer with modes**, not a set of `if` statements inside each action.
6. **Classifying commands by their text is fragile.** Use a sandbox or a minimal list.
7. **The order of execution is part of the contract with the model.** Results come back in request order, and edits do not run in parallel.

## Exercises

1. Implement a `search_replace` action with a uniqueness check on the fragment. Verify that a fragment occurring twice produces an error rather than a replacement of the first occurrence.
2. Write a `FileChange` with "before" and "after" fields and implement the rollback. Check three cases: modification, creation, and deletion of a file.
3. Implement a "read-only" command classifier for three commands: `ls`, `cat`, `grep`. Then try to bypass it with a command that writes a file (hint: the `>` redirection, and options that write files). Fix the classifier and add a test for each bypass.
4. Simulate a model response with three actions (two reads and one edit). Check that the results come back in request order and that the edit does not overlap with the reads.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The classes and instructions were checked against HEAD. The quotation from the `search_replace` instructions is abridged.
