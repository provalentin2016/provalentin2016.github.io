# Chapter 20. How a Team and Agents Ship Code Together

The last chapter of the book is not about the agent but about the people and agents who build it. Over three years the repository's history has acquired about two hundred authors. Roughly a fifth of the commits from the last year carry the trace of Junie: a co-author line. Agents write code, review it, close tasks, and update documentation. And there are fewer people than there are changes.

A natural question follows: how do you keep the parallel work of people and agents from turning into chaos? The answer in this repository is not a single tool but a set of written rules, skills, and automation. This chapter goes through them and shows which decisions work and which exist so far only on paper.

## 20.1. Rules for everyone: one file

The main document is `AGENTS.md`. It is written for people and agents at the same time: both the developer and Junie read it before starting work. The file is divided into sections: code style, serialization and HTTP without reflection, coroutines, tests, the repository, pull requests. At the beginning of the repository section stands a rule that looks like a detail: do not commit files from `.junie/plans/`. Plans are the agent's local working materials, and if they entered the history, the history would stop reflecting the code.

The section on pull requests is written more strictly than the others and refers to a separate skill. The rule reads: every change lands in `main` through a mandatory pull request, and an agent making a change is obliged to read the skill before it starts.

Why do the rules have to live in one place? Because without them, agents and people work from different notions of what is normal. An agent that does not know a PR should be one logical unit will produce a huge PR. A person who does not know about the size guideline will submit "part 1 of 2", which cannot be reviewed on its own.

## 20.2. The skill: a rule that can be applied

`AGENTS.md` says what to do. A skill says how to check it. The repository has more than forty skills in the directory `.agents/skills/`: from `pull-requests` and `teamcity-build-investigation` to `acp-extensions` and `coroutines-and-dispatchers`. Each skill is a short document describing when to apply it, along with its rules.

The `pull-requests` skill states its main rule in one sentence: **a PR contains one logical change**. A change is something that can be described in one sentence without the word "and". If that is impossible, it must be split. But splitting is justified only when each part has its own rationale, passes its tests on its own, and can be reverted separately.

Now about size. The skill says: size is a secondary signal. The signal is the number of added lines of production code: above 200, re-check that the PR is one change; above 400, explain why in the "Notes" section. The script `scripts/pr-size.sh` counts the lines, and the PR template asks for the result. Size does not decide whether a PR may be accepted; it only indicates where to look more carefully.

There is a subtle distinction here. The rule "do not split artificially" forbids splitting for the sake of size: "a PR with code that nobody uses until the next PR", "part 1 of 2". Such a cut is worse than a large cohesive PR, because no part can be judged on its own, and `main` ends up holding half of a change. The rule protects against bureaucracy in both directions: against giants and against artificial fragmentation.

## 20.3. The template: four questions for every PR

The pull request template is small but telling. It has four sections:

- **Why** — the problem or motivation, with a link to the task.
- **What** — what changed, at the level a reviewer needs: behavior, new and removed APIs, configuration, migrations. Not a list of files.
- **Validation** — which tests were added, which commands were run, what was checked by hand. And separately: what was not verified.
- **Notes** — risks, follow-up steps, excluded scope.

The most interesting section is Validation. The requirement "never claim a check that did not happen" is written into the skill plainly, and the template reminds of it. This matters for agents: a model tends to write "tested" without running the tests. The template makes the omission visible.

## 20.4. Automated review: who checks the agent

Every PR into `main` goes through the review workflow `junie-review`. It runs Junie on the change through GitHub's official action and asks it to assess the code. The environment `junie-review` restricts access to secrets. The review runs when a PR is opened, moved out of draft, and on every update.

But the agent's review is not the last word. The skill describes rules for those who review: approve when a change improves the overall health of the code, even if it is not perfect; style comments do not block; misleading comments must be flagged, while harmless explanations should be ignored.

More important is this: **a PR created by a bot is not approved by the bot**. It needs a human's approval. The person who approves is responsible for the PR's description and for the bot's verdict. Not for reading every line, but for understanding what changes and why.

That is how responsibility is divided. An agent may review, but it cannot decide to merge a change that it wrote itself. This simple rule closes a whole class of problems that arise when a system checks itself.

## 20.5. CI checks: what cannot be bypassed

The README lists the mandatory checks. A merge is forbidden if any of them has failed or did not run:

1. `Check Redis Cache` — the cache of model requests (Chapter 10).
2. `Check Agent Execution` — the check of the agent's execution.
3. `Check Redis Cache (Standalone)` — the unchanged state of outgoing model requests.
4. `Build & Check v***` — the build and general checks.

The README states plainly: "Merging ... is forbidden". The wording "or did not run" matters here. A skipped check does not count as passed. This closes a common loophole: a PR whose CI has not started yet, but which gets merged "in hope".

It is also recorded that the checks sometimes start 10 to 20 minutes after the PR is submitted. The document warns about this in advance, so that a person does not mistake the delay for a breakage.

## 20.6. Process commands: specifications in a loop

The directory `.junie/commands/` holds commands that the agent executes according to a script. There are commands for releasing (`create-release-branch`, `release-cli-tickets`, `get-next-release`), for working with the journal (`recap`), and a group `spec-*`: `spec-list`, `spec-take-next`, `spec-auto`, `spec-loop`, `spec-inter`, `spec-update`, `spec-deprecate`.

The `spec-*` group shows how the process became part of automation. The command `spec-loop` repeats `spec-take-next` while the specification index still contains rows marked "no spec". Each iteration writes one specification in autonomous mode and updates the index row. The description says plainly: this is batch work, the user need not be available between iterations, and whatever the autonomous run cannot resolve is flagged for manual review.

Here a shift is visible. Previously a person wrote a specification and then it was reviewed. Now an agent can generate dozens of specifications from the index in one go, and a person checks the result. This is advantageous, but it creates a risk: a specification that nobody has read is a hypothesis (Chapter 16 made the same point about the cost specification).

## 20.7. Traces of the agent in the history

Commits that the agent created carry the co-author line `Co-authored-by: Junie`. In 2026 there were about 1,460 such commits out of roughly 7,400. The exact share changes, but the order of magnitude is clear: about one commit in five this year involved the agent.

It is useful to see this in the history. From the co-author line one can tell which parts of the code were written with the agent's help, and check how they went through review. But the line does not say how well the person understood the change. That is the responsibility the skill records: the approving person is accountable for the description and the verdict.

For the book this is an important fact. The history of the repository is not only an archive of people's decisions but also a log of collaboration. Reading it today means seeing where a person wrote, where the agent did, and where they disagreed.

## 20.8. What works and what is still on paper

An honest summary. The rules work where automation enforces them: the CI checks, the PR template, the size measured by a script, the ban on merging with a skipped check. Rules that depend on people's attention are weaker: "do not claim a check that did not happen", "read the specification". The template and the skill make these violations visible, but do not prevent them.

The history also shows that the process is changing. Skills appeared in February 2026 and lived in `.junie/skills`, that is, they were tied to a single agent. On 9 November 2026 the commit "Move team rules and skills to cross-agent AGENTS.md and .agents/skills" moved them into `.agents/skills` and `AGENTS.md`, so that agents other than Junie could read them too. The rules stopped being a personal tool of one agent and became a shared document of the team.

Another signal: the number of authors. In the history leading to the current HEAD there are about two hundred authors, and in 2026 about a hundred and thirty of them were active. The scale of a team demands shared rules, and shared rules demand skills that both a person and an agent can read.

## 20.9. What follows

1. **Write the rules once, for everyone.** A person and an agent should read the same document.
2. **A skill turns a rule into a check.** State when to apply it and how to verify it.
3. **One logical change per PR.** Size is a signal, not a law. Artificial splitting is worse than a large PR.
4. **The PR template forces you to name the checks and their gaps.** Do not claim what did not happen.
5. **A bot does not approve its own PRs.** Responsibility for merging lies with a person.
6. **A skipped check is not a passed one.** A merge is forbidden if CI did not run.
7. **A specification nobody has read is a hypothesis.** Automatic generation does not replace verification.
8. **The history is a log of collaboration.** Mark where the agent took part.

## Exercises

1. Write an `AGENTS.md` for your project: three sections — style, tests, PR rules. For each rule, state who checks it: a person, the agent, or automation.
2. Add a `pull-requests` skill with the rule of one logical change and a script that counts lines. Verify that the script counts only production code, and that tests and documentation are not included in the count.
3. Set up a PR template with the sections Why, What, Validation, Notes. Verify that the Validation section requires you to state explicitly what was not verified.
4. Write a list of mandatory checks and a rule: a skipped check blocks the merge. Verify that a PR without a completed check cannot be merged.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles. The rules are in `AGENTS.md`, the skill in `.agents/skills/pull-requests/SKILL.md`, the template in `.github/pull_request_template.md`, the list of checks in `README.md`, the commands in `.junie/commands/`, and the automated review in `.github/workflows/junie-review.yml`. The counts of commits and authors were obtained through `git log` on HEAD; the number of authors in the chapter (about two hundred) refers to the history leading to HEAD, not to all branches.
