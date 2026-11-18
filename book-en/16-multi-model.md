# Chapter 16. Many Models: Selection, Configuration, and Cost

[← Previous](15-sandbox.md) · [Contents](README.md) · [Next →](17-acp.md)

Models change faster than the agent does. Over two years the project's history acquired models from several families, each with its own reasoning parameters, its own tool constraints, and its own price. A new model appears every few months, and if each one required a branch of code, the agent would quickly turn into a collection of exceptions.

This chapter is about how the agent holds many models within one architecture: how selection is separated from execution, how effort levels are organized, why an economy mode appeared, and how the model catalog became a public contract. The last point is unexpected, but important.

## 16.1. Three layers: selection, provider, execution

The repository skill `llm-proxies-and-models` describes the architecture in three layers, which is the best way to understand it:

1. **Model selection** (`ModelOption`) — what the user specified with a flag or in the interface. There are two kinds: a built-in model (`Specific`) and a user-defined profile (`Custom`).
2. **Provider** (`LLMProviderEntity`) — who provides access and with which keys.
3. **Execution** (`LLMProxyImpl`) — sending the request and parsing the response.

This separation makes it possible to change the model without touching the execution, and to change the provider without touching the selection. If selection were tightly bound to the provider, every change of provider would become a rewrite.

## 16.2. Aliases: stable names over changing models

A user should not need to know that "the smartest model" is called one name today and another in six months. Aliases exist for this purpose. The enumeration `ModelAlias` (introduced 26 February 2026) maps stable short names (`gpt`, `opus`, `sonnet`, and others) to concrete `ModelOption` values:

```kotlin
enum class ModelAlias(val alias: String, val modelOption: ModelOption) {
  GPT("gpt", ModelOption.Specific.GPT6_1_SOL),
  GPT_CODEX("gpt-codex", ModelOption.Specific.GPT5_3_CODEX),
  ...
}
```

The user writes `gpt`; today it is one model, tomorrow another. Re-pointing an alias is one line of code, not a migration of every configuration.

There is also an internal alias, `small`: a model for secondary tasks (subagents, commands, skills). It is deliberately invisible to the user. The documentation says so directly: the alias is an authoring detail and "must never reach the user". The display name `small` shows the concrete model of the same provider. The subtlety is that the user should not see an internal abstraction, even if it helps the code.

One more detail: `LLM.equals` compares only the name and the provider, while routing uses a key that includes one more attribute. Two aliases of the same model can count as equal while leading to different routes. This is a classic object-comparison trap, where equality does not coincide with identity for execution.

## 16.3. Effort levels: not all models are the same

Many modern models can "think" for longer: they spend tokens on internal reasoning before answering. The degree of that reasoning is set by an effort level (`EffortLevel`). The enumeration appeared on 16 April 2026 and has seven values: from `None` and `Minimal` through `Low`, `Medium`, `High`, and `XHigh` up to `Max`.

The key feature is that **not every level is available for every model**. The method `next()` moves to the next level from the list of available ones, not from the full list. The model's configuration says which levels it supports. If the user asks for a level that does not exist, the system should choose the nearest permitted one, rather than fail.

Effort levels are also inherited by subagents (Chapter 9), with one exception. A subagent that answers questions about the documentation is forced to the lowest level: its job is not to reason but to quote. Here the exception is justified by the task, not by the model.

## 16.4. Model quirks that cannot be ignored

Several cases show that models behave differently even behind the same interface.

**Sequential tools.** Some models, in particular those from the xAI and Gemini families, often call several tools in one response and expect them to run in order. The code in `AgentActionsExecutor` takes this explicitly into account: for such models the actions run sequentially, if the response contains no subagents. The commit that did this appeared on 13 October 2026 (Chapter 8).

**Anthropic adaptive thinking.** For models with adaptive thinking, the reasoning budget is given by the special value `0`, not by a number of tokens. According to the description in the skill, if this value is sent as an ordinary budget, the request breaks. A subagent inherits the parent's budget, and if its model does not support the adaptive mode, the value `0` goes into the request as an ordinary number. That is why the code has a check, `isAnthropicAdaptiveThinkingSupported`.

**Auxiliary calls.** For some hosted models, auxiliary calls (summaries, classification) run on the main model itself. For others they run on a separate light model. The choice depends on what the provider supports, and it is determined by the function `runsAuxiliaryCallsOnItself`, not by assumption.

The general rule: **a model is not only a name but also a set of behaviors**. The order of tools, the shape of the reasoning budget, and the route of auxiliary calls differ. An agent that treats models as interchangeable will break at every change.

## 16.5. Economy mode: planning on a strong model

The most practical idea in this chapter is the Eco mode. The documentation describes it directly: when the mode is on, Junie plans the task with the selected model and implements the change with a cheaper model. The logic is simple: planning determines quality, while implementation consumes more tokens. So the strong model is kept where it decides, and the weaker one is used where the volume is large.

The document also gives an assessment: on the team's internal benchmarks for programming tasks, this approach delivers roughly the same quality at about half the price. This is a claim made by the developers, not an independent measurement, and the reader should treat it as a hypothesis worth testing on their own tasks.

The mode is switched by a toggle, and the preference is stored separately for each model. The toggle appeared in September 2026 ("Add eco-mode toggle"). In the code it is passed as an attachment to the task request, and the main agent takes it into account when choosing the model for implementation.

A related idea is **Junie Mix**: ready-made profiles with the levels `lite`, `normal`, `hard`, and `frontier`. The catalog of profiles comes from a feature flag and is validated when parsed: an incorrect schema version or an unknown level is rejected, not partially applied. The user picks a level, not a combination of model and effort.

This is a good example of how complexity is hidden. Inside are pairs of models, effort levels, and economy modes. Outside are four words.

## 16.6. The model catalog as a public contract

The unexpected part of this chapter: the list of models and their capabilities has become a **public contract** for integrations. With each ACP build a file, `junie-agent-model-configuration.json`, is published. It lists the public models, the mapping of models to providers, the supported thinking levels, the default level, and the availability of the economy mode for each model–level pair.

The file sits next to the binary and has a version equal to the release tag. Editors and IDEs read it to offer the right choices, without hard-coding the list of models into themselves. This is the decision from Chapter 12 (the ACP protocol) and Chapter 11 (the external contract), applied to models.

The semantics of the file are carefully thought out. The absence of an entry for the economy mode means "not supported", not "enabled by default". Every published key carries `"default": true`, which reflects the behavior of Junie itself. Such rules are documented because integrations rely on them.

The publication entered the history on 18 November 2026 ("Publish model list per release to ACP registry"). Before that, the list of models lived only in the clients, and every update required a synchronized change in all integrations.

## 16.7. Cost: accounting that is not hard-coded

Model prices change, and a price table in the code goes stale quickly. Chapter 5 showed the first version: prices written directly into the cost-calculation function. In 2026 the cost accounting was moved into a specification. The file `docs/specs/token-usage-and-costs.spec.md` describes the behavior, the entry points, the edge cases, the lifecycle, and the acceptance criteria. Its first version appeared on 29 April 2026, and the commit itself carries a "Review needed" note: the specification was generated, but has not yet been reviewed.

This is an honest position. A specification that nobody has reviewed is a hypothesis about behavior, not a description of it. For the book it is useful that it shows how cost accounting moved from code into a document, and that the document itself requires verification.

Cost accounting still lives in the execution context (Chapter 7): each node accumulates tokens and cost, and the root aggregates them. Only the source of the prices has changed.

## 16.8. Chronology

- **6 December 2025** — models of the Grok family; a check `isXAI` appears in the code.
- **26 February 2026** — model aliases.
- **16 April 2026** — effort levels (`EffortLevel`).
- **29 April 2026** — the specification of token and cost accounting.
- **29 September 2026** — the economy-mode toggle.
- **13 October 2026** — sequential execution of tools for models that expect it.
- **18 November 2026** — publication of the model catalog for ACP.

It is clear that over 2026 the architecture shifted from "one model, supported by hand" to "selection through aliases and profiles, with behavior described as data and the catalog published as a contract".

## 16.9. What follows

1. **Separate model selection from execution.** A change of provider must not touch the selection.
2. **Use stable aliases.** The user writes a name that does not change, and the code re-points it to a model.
3. **Models differ in behavior**: the order of tools, the shape of the reasoning budget, the route of auxiliary calls.
4. **Not every level is available for every model.** The configuration must say what is permitted.
5. **Put the strong model on planning and the weaker one on implementation**, but measure this on your own tasks.
6. **The model catalog is a public contract.** Publish it with a version and explicit rules for missing fields.
7. **Call a specification you have not verified a hypothesis.**

## Exercises

1. Implement model selection through aliases: `gpt` and `fast` lead to different concrete models. Re-point `gpt` to another model in one line and verify that user configurations do not change.
2. For two models, describe the available effort levels. Implement `next()` that moves only through available levels. Check the case where the requested level does not exist for the model.
3. Implement the economy mode: one model plans, another implements. Measure cost and quality on five of your own tasks in both modes, and compare with the document's claim about half the price.
4. Publish a JSON catalog of your models with a version and the rule "a missing field means not supported". Write a client that reads the catalog and does not hard-code the list of models.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The architecture comes from `.agents/skills/llm-proxies-and-models/SKILL.md` and the code in `core/.../llm/`. The public catalog comes from `docs/agent-model-configuration.md`. The economy mode comes from `documentation/topics/Junie-Eco.md`. The "half the price" assessment is a claim from the documentation, which I have not verified.
