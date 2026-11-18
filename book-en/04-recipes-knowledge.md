# Chapter 4. Recipes: Knowledge the Agent Should Not Invent

[← Previous](03-parallel-and-benchmarks.md) · [Contents](README.md) · [Next →](05-reliability.md)

A model knows a lot, but not everything, and it certainly does not know how to wire Google OAuth into an Express application today, or which version of a library to install. If nobody tells it, it will invent. Sometimes it invents well; more often it invents APIs that do not exist, or libraries that should not be used.

Matterhorn solved this with **recipes**: verified instructions with code examples that the agent can attach to a task. A recipe is not just documentation. It is a structured object with a description, dependencies, code fragments, and rules for applying it.

This chapter is one of the most instructive, but with a caveat that must be known from the start: **the current HEAD of the repository has no recipe catalog**. It lived in the generator subsystem, which was removed in November 2025. More on this at the end of the chapter.

## 4.1. The problem: the model does not know the latest versions

In April 2024 Matterhorn generated applications that used external services: Google Calendar, Google Sheets, OpenAI, Slack. The model knew these APIs from its training data, but:

- it did not know the current version of the client library;
- it confused the OAuth parameters;
- it did not know that the project already had the needed dependency, or what had to be installed.

The first answer was obvious: put the documentation into the prompt. But documentation is long, and context is expensive. What was needed was a mechanism that selects only the relevant knowledge.

## 4.2. The catalog and the index

The first commit is `Basic implementation of recipe catalog` (18 April 2024, task). The idea: recipes live in the plugin's resources, each is described in a `*.recipe.yaml` file, and the model receives only an index: a short list of paths and descriptions.

The scheme in simplified form:

```
Task from the user
   └─ RecipeLookupWorker
        ├─ receives the index: [{path, description}, ...]   ← short
        ├─ the model selects the paths of suitable recipes  ← JSON array
        ├─ check: is the path in the index?                 ← UserReviewedRequest
        └─ recipes + their dependencies → into the generator's prompt ← full instructions
```

The worker `RecipeLookupWorker` appeared in the commit of 29 April 2024. The key detail in the code: the model must return a JSON array of paths, and each path is checked against the index:

```kotlin
return@UserReviewedRequest "Path '$path' doesn't have corresponding knowledge base entry"
```

If the model invented a path, the answer is rejected: the model gets an error message and tries again. This is the same `UserReviewedRequest` mechanism as in Chapter 2 for the action format. The check runs on the code's side; the model is not trusted.

Why the index matters rather than the full catalog: the model chooses from a short list, and only the selected recipes receive their full text. This saves context and reduces noise.

## 4.3. The structure of a recipe

The structure of a recipe changed several times. The first formal version is described in the commit of 30 April 2024, through documentation comments in `RecipeContent.kt`:

```kotlin
@Serializable
open class RecipeContent(
  val topics: List<String> = emptyList(),      // 1–2 words, categories
  val description: String,                     // goes into the index
  val depends_on: List<String> = emptyList(),  // recipes to apply first
  val instructions: String                     // instructions for the model
)
```

There are three distinct purposes here. `description` is only for choosing a recipe. `instructions` are only for applying it. `depends_on` is for ordering. The separation matters: a description written for a model that is choosing something differs from an instruction for a model that is writing code.

Later the structure grew richer. The recipe file for Google OAuth, in a later version, looks like this:

```yaml
topics:
  - "google authentication"
description: |-
  How to access Google APIs for OAuth authentication.
scopes:
  - Backend
dependencies:
  - "googleapis@135.0.0"
snippets:
  - source: src/GoogleAuthService.ts
    target: src/services/GoogleAuthService.ts
  - source: src/GoogleAuthController.ts
    target: src/controllers/GoogleAuthController.ts
instructions: |-
  # Initialize GoogleAuthService.
  ...
```

New fields appeared as they were needed:

- `scopes` (22 May 2024). The recipe states whether it is for the backend or the frontend (`RecipeScope`: `Frontend`, `Backend`). Judging by the task's title, the need was a way to keep a recipe from being applied to the wrong part of the project.
- `snippets` (commit of 7 May 2024). Instead of describing code in words, a recipe can contain a ready-made file. Judging by the code (`snippet.source` → `snippet.target`), this is a way to pass library code without paraphrasing it.
- `protected` (commit of 7 June 2024, "Add an option to mark recipe snippets as protected"). Fragments with this mark are treated as protected. The exact behavior is not described in the commit message; it should be checked in the code.
- `dependencies` with a pinned version. The commit of 7 May 2024, "Set version of googleapis library in the recipe", fixes the version in the recipe rather than letting the model choose it.

## 4.4. Dependencies: what the agent may install

An agent that can run `npm install` can install anything. That is dangerous both for security and for stability. Matterhorn limited this in two steps.

**Step one: an allowlist.** The commit of 18 April 2024, `whitelist installed npm dependencies`. The logic is in `NpmRunWorker`: if no list of approved dependencies is set, the package is installed at its latest version without checking. If the list is set and the package is not in it, the operation is rejected. The list lives in the project at `.llm/dependencies.json`, and the rejection message refers to it directly:

```
<package> is not in the list of approved dependencies.
See `.llm/dependencies.json` for the list of approved dependencies.
```

**Step two: a check before installation.** The commit of 7 May 2024, `Check that requested dependencies exist`, added `AddNpmDependencyProjectAction`. Its `review` method runs `npm add --dry-run`: the command attempts the installation without writing to disk. If the package does not exist or the version is not found, the model gets an error before anything has changed.

Notice the order: first the allowlist check, then the dry run, and only then the real installation. Each step is cheaper than the previous one, and a rejection at any step leaves no trace.

The commit of 6 May 2024 added automatic installation of a recipe's dependencies ("Install required npm dependencies automatically"). Now installation proceeds from the recipe, not from the model's decision.

## 4.5. An error that was rolled back

The most instructive episode is `Embed recipe for config into template and guidelines` (14 May 2024). The idea: embed the configuration recipe directly into the template and the instructions, so the model would not have to recall how to read `.env`. Three weeks later it was rolled back: `Revert "...config..."` (4 June 2024), and at the same time `Rollback config from templates and return to the good old process.env` (4 June 2024).

The reason is not recorded in the commit messages. The sequence of events shows that the decision was not to explain the configuration better, but to return to a simple mechanism that the model cannot get wrong: an environment variable (`process.env`). On the same day, `Hardcode backend port in the template` (added 17 May, reverted 4 June) was also rolled back: the backend port had also been baked into the template.

The lesson for the book: **a recipe is useful for knowledge that the model may apply in different ways, and harmful for things that must be unambiguous**. Configuration is better set by code than by text.

## 4.6. Rules that came from mistakes

Recipes grew as the agent made mistakes. The clearest example is the SQLite recipe. It appeared in the commit of 17 July 2024 and then received a series of edits:

- `Add a line about unsupported operator to SQLite recipe` (26 July 2024);
- `Add examples to rules in SQLite recipe` (29 July 2024);
- `Add a rule about managing write operations to SQLite recipe` (12 August 2024).

Each edit is a rule that appeared after a specific mistake. This is a manual analogue of what is now called "evals": a mistake is recorded, and a rule is fixed in the knowledge. The recipe becomes a history of its failures.

The same logic is visible in the OpenAI recipe: `Add a rule about model usage to the openai recipe` (6 August 2024). The commit message does not describe a specific mistake, so the link to one is a guess; the fact that the rule was added is recorded.

## 4.7. Recipes for the frontend and project assembly

In August 2024 the recipes split by frontend: `Add recipes for frontend (antd and bootstrap)` (20 August 2024), then `shadcn` (2 September 2024) and `animations` (3 September 2024). The choice of UI library became a separate decision made by a recipe, not by the model. The commit of 20 August 2024 clarifies: if no library is specified, antd is used by default.

Two commits show how recipes were woven into the flow:

- `Let SWE know about guidelines and recipes` (28 August 2024). The agent with the loop from Chapter 2 now sees the recipes.
- `Add paths to all recipes to prompt` (30 August 2024). Recipe paths entered the prompt, so the agent could refer to them by name.

## 4.8. The boundary: what a recipe does not solve

A recipe does not replace verification. Even a correct recipe can be applied incorrectly by the model. That is why the history always placed checks next to recipes: compilation, tests, the dry run, the allowlist (Chapters 3 and 5).

The code has one more limitation worth knowing. The function `RecipeCatalog.lookup` walks `depends_on` recursively:

```kotlin
fun lookup(recipePath: String): List<Recipe> {
  val recipe = recipes[recipePath] ?: return emptyList()
  return recipe.content.depends_on.flatMap { lookup(it) } + recipe
}
```

In the version from the commit I examined, there is no cycle check: if recipe A depends on B and B depends on A, the recursion never stops. I checked exactly this version. In practice the catalog apparently contained no cycles, but the code gives no guarantee. For your own implementation this is an error worth preventing right away: a `visited` set solves it in three lines.

## 4.9. What became of the recipes

Here we need to be precise, because this changes the meaning of the whole chapter.

- The recipe catalog lived in `webgen-main/src/main/resources/recipes/` and in the related `webgen/recipes/` packages.
- The last commit related to recipes is dated 13 October 2025: `[declarative-generator] Support env variables for recipes`.
- The commit of 28 November 2025, `Remove Kineto`, deleted 1577 files and 151,412 lines. Among the deleted files were 264 with "recipe" in their path, including `webgen/recipes/RecipeCatalog.kt`, `RecipeContent.kt`, `workers/RecipeLookupWorker.kt`, `workers/RecipeApplyWorker.kt`, and the resources `recipes/shadcn` and `recipes/custom-ui-components`.
- HEAD contains no `*.recipe.yaml` files, and `RecipeCatalog` is absent.

What survived into the current code is the `UserReviewedRequest` mechanism (`core/src/main/kotlin/.../requests/UserReviewedRequest.kt`), which checks the format of the model's answer. It is used both by the agent from Chapter 2 and by the index lookup from this chapter in its original version. The idea "the model chooses from an index, the code checks the choice" outlived the specific implementation.

The takeaway for the book: this chapter describes a real mechanism that worked and was removed together with the generator. That is not a failure, but the reader should know that the current Junie is built differently and should not look for recipes in the current code.

## Exercises

1. Create a catalog of 5–10 recipes in YAML: `description`, `depends_on`, `instructions`. Implement lookup: the model receives only the index of `description` values, returns a JSON array of paths, and the code checks each path against the index and rejects invented ones.
2. Add to a recipe a dependency that forms a cycle (A → B → A). Check that your `lookup` hangs or fails. Then add `visited`.
3. Find a task on which the model makes the same mistake consistently. Write one rule into a recipe, run the same task, and compare the results. This is the minimal version of the "mistake → rule" cycle.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates.
