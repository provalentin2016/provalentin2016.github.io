# Conclusion

[← Previous](22-timeline.md) · [Contents](README.md)

Twenty-two chapters later, it is worth asking what the history actually teaches. Not the list of features, which changes every release, but the patterns that held across two and a half years and several rewrites.

## What stayed the same

The core of the agent is a loop: the model chooses an action, the environment executes it, and the result returns to the model as an observation. That loop appeared in April 2024 and is still at the heart of the system. The pieces around it changed, but the loop did not.

The execution context is a tree. The root owns the resources of a task, and each request is a node that accounts for its own time and cost. Without this split, cancellation, cleanup, and budgets would have been tangled together. The current code keeps the split, and the rules around it are written as tests that describe the required behavior.

Artifacts with explicit results are a second survivor. The Matterhorn pipeline produced artifacts that could be inspected, re-run, and invalidated. The current agent produces file changes, tool results, and subagent outputs, each with a clear identity. The vocabulary changed, but the idea that a step leaves a visible, correctable result did not.

## What had to be learned the hard way

The first lesson concerns the model's output. A format that works on one model breaks on the next, and a response that the code cannot parse ends the loop. The team's answer was to make the format a contract: explicit examples in the prompt, checks in code, and tests whose failures show exactly which request changed. Chapter 10 describes the cache that makes such changes visible in review.

The second lesson concerns failure. Retries need limits and delays, and an infinite retry is a missing policy rather than a policy. Cancellation must reach the whole tree and must not be swallowed. A command that hangs needs a timeout and a way to be killed. A budget must be checked where every call is visible. These rules sound obvious, and the history shows that each one was learned after a failure that did not have them.

The third lesson concerns boundaries. The split between the core and the IDE modules, the separation of people from logins in the service's data model, the rule that a bot does not approve its own pull requests, and the rule that an extension is enabled by a negotiated capability and not by a client's identity are all the same idea. A boundary is useful when it is explicit, checked by something other than a person's attention, and documented together with the places where it leaks.

The fourth lesson concerns names and contracts. Internal names can change freely. Names that reach the disk, the network, or the user's environment are contracts, and changing them needs a period in which both names are accepted. The environment variables and serialized class names in the current code show that the team learned this, and also that the transition is never quite finished.

The fifth lesson concerns honesty about the system's limits. The sandbox does not execute without a shell. The ACP layer has a published list of places where it ignores its own rules. The Junie Live design document lists five gaps, from ordering to stuck commands. The team did not hide these, and the book is more useful because of them.

## What changed direction

In 2024 the question was how to make the model do the work. In 2025 it became how to make the work reliable across several environments: the IDE, the terminal, the editor, a server. In 2026 the question became how to govern the agent: which tools it sees, which models it uses, which changes need a human, and how much it costs.

The architecture moved accordingly. A single plugin became a set of modules, then an application with several modes, then a set of protocols with versions and capabilities, then a service with a data model. Each step kept the core and changed the shell around it, which is why the core survived the removal of the IDE line.

## Principles, in brief

1. Build the loop first, and make every step leave an observation the model can see.
2. Treat the response format as a contract, and test it whenever the model changes.
3. Give every resource an owner, and close it exactly once.
4. Give every long operation a limit, a timeout, and a way to be cancelled.
5. Check a budget at the single point where all calls pass.
6. Refuse ambiguous edits instead of guessing, and keep both the before and the after.
7. Confirm what is risky, and sandbox what must not be allowed by default.
8. Keep the core free of the shell it runs in, and keep the shell replaceable.
9. Negotiate versions and capabilities; do not infer them from identity.
10. Publish the catalogs and contracts that other systems depend on, with versions.
11. Record your known gaps, and attach a ticket to each one.
12. Let the process itself be checked by something that does not get tired.

## What the book does not cover

The book does not give a complete design of an agent, a comparison with other agents, or measured quality. It does not describe the server side of Junie Live, which lives outside this repository. It does not explain how the model itself is trained or why it behaves as it does. Where the history records a decision without a reason, the book says so.

It also reflects one team at one time. Other teams would make different choices about the same trade-offs, and some of the choices here were made under constraints that may no longer hold. The value of the book is less in the specific answers than in the questions the history shows being asked, and in the order in which they came up.

## Where to go next

If you are going to build an agent, start with the companion code and make the loop work on a small task. Add the edit with a uniqueness check, then the budget, then the cache. Add the second client only when the first one is stable. Write down your gaps as you find them.

If you are going to maintain an agent, read the design documents in the repository before you change the code they describe. Most of the reasons behind the current shape are written down there, and most of the surprises come from changing something whose reason you did not know.
