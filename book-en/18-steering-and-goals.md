# Chapter 18. Steering a Running Agent: Steering and Goals

An agent works for minutes, sometimes for hours. The user sees that it has gone the wrong way, or remembers an important requirement, or wants to change priorities. What can be done? In an ordinary chat the options are: wait for the turn to end and write again, or stop the agent and start over. Both are bad: the first is slow, the second throws away the work already done.

This chapter covers two mechanisms that tackle this problem from different sides. **Steering** is sending a message while work is in progress, without waiting for the turn to end. **Goal** makes the goal itself a state of the session: the agent knows what it is aiming for, and the client can see and change it. Both are built as ACP extensions (Chapter 17), and both taught a lesson about what a "turn" is and what a "task" is.

## 18.1. A message during work

Steering allows the client to send a follow-up while the task is still running. The protocol describes two successful outcomes, and neither is an error:

- **`injected`** — the task was still running, and the message was added to it, so the agent will take it into account in its work.
- **`startedNewTurn`** — the task finished before the agent handled the request. The message is not lost: the agent started a new turn and carried it out.

The wording of the contract is strict: a message is **never lost**, and a request that arrives "too late" is **never returned as a JSON-RPC error**. This is an important decision. If lateness were an error, the client would have to decide for itself what to do, and every client would decide differently. So the race between the end of a turn and a message is resolved inside the agent.

Why this is hard. The agent works in a loop (Chapter 2), and a message can arrive at any moment: during a model call, during a file edit, between steps. For each case a decision is needed: add the message to the current turn or start a new one. The decision depends on what has already happened. The document describes this as "decisions by turn phase" (`Decision by turn phase`).

## 18.2. Commands during work

The most delicate spot is slash commands. The user may type `/stats` or `/plan close` while the agent is working. Such commands cannot be sent to the model as ordinary text: the model would receive the string `/stats` and answer it as if it were a question.

The solution: commands are divided into three classes.

1. **Commands that work within the current turn** (`SteerableAcpCommand`): status, mode switches, `/mcp`, `/sandbox`, `/plan close`, `/goal close`. They run at once and emit updates, without sending anything to the model.
2. **Commands that extend the prompt** (`/<skill>`, `/<custom>`). They are expanded and inserted into the running task as an additional instruction.
3. **Commands that start a new task or change the global state** (`/compress`, `/rollback`, `/new`, `/review`, `/goal <task>`, `/plan <task>`). During a turn they are rejected with the code `steering_turn_busy`.

The third class is the most important. The command `/rollback` during work would roll back the files the agent is changing right now. `/new` would leave the task hanging. So they are forbidden, and the refusal carries a clear code rather than being silently ignored.

Notice how this classification grew. The class `SteerableAcpCommand` appeared on 2 November 2026 ("fix /remote command state and slash-command steering"), a few months after steering itself. Judging by the commit title, before that the behavior of commands during work was fixed one by one. Each command received an explicit decision about which class it belongs to. There are about twenty-two references to this class in `ej-app`.

## 18.3. Why "never lose" is a rule, not a convenience

Imagine a client that sends a message just as the agent has finished. If the message is lost, the user writes it again and then realizes that the agent did nothing. If the message lands in a new turn, the user sees a response. The first is a silent failure; the second is a working system.

The rule "never lose" requires that the agent has a queue, or at least an explicit mechanism for "start a new turn". It is a simple idea, but easy to break: a single code path where a message arriving at the wrong moment is simply dropped is enough. That is why the document records the rule as a contract rather than as a wish.

## 18.4. Goals: state, not one request

The second half of the chapter is the **Goal** extension. The document's idea is stated in its title: "a goal is session state, not one prompt". A goal lives longer than a single request. The status `active` means the goal may drive further work. It does **not** mean that a prompt is executing right now.

For the client this changes the interaction model. Before, the user sent a task and waited. Now the user sets a goal, which the agent holds, and can change it without sending a new prompt. This is closer to how people work: a manager sets a direction, not every step.

The protocol describes three surfaces:
- the agent declares goal support in `initialize`;
- the client controls the goal through the method `_session/goal` with the actions `set` and `clear`;
- the state of the goal is available to the client.

Junie declares `["set", "clear"]`: it can set and close a goal, but it **cannot** pause or resume one. The document does not hide this limitation: the capability declaration lists exactly what is implemented.

The `goal` key in the capability declaration is **absent** when goal mode is unavailable, rather than present with an empty value `{}`. The difference matters: a client that sees an empty object may conclude that goals are supported but without actions. The absence of the key unambiguously means "no".

## 18.5. Availability conditions: client and model

A goal is available in version v2 only under two conditions: the client declares support for the confirmation form (`elicitation.form`), and the current model supports goals. The second check is tied to models (Chapter 16): not every model is suitable for long goal-directed work. The same policy governs the discovery of the `/goal` command, the configuration value `goal`, and the check of a plan before it is turned into a goal.

Notice that the check is repeated after a model change. A goal available on one model may disappear on another, and the client must learn this, not discover it through an error when it tries.

## 18.6. Plan and goal: two modes that are easy to confuse

Goals are closely tied to the planning mode. The command `/plan` switches the session into a mode in which the agent first drafts a plan and then works according to it. The document describes subtle rules:

- a repeated `/plan` command does not switch the mode off;
- `/plan close` returns to the normal mode and **stops the running goal**, not only the planning;
- the plan file stays on disk even when planning is closed;
- `/plan <task>` starts from a clean state and creates a new file, rather than reusing the closed one.

These rules seem pedantic, but each one closes a specific error. If `/plan close` left the goal running, the user would think the agent had stopped, while it continued changing files. If a repeated `/plan` switched the mode off, an accidental double press would silently cancel planning.

A rule worth remembering: **a closing command must stop everything it promises to close, and nothing more**. The plan file is user data, so it is kept.

## 18.7. What the second wave brought

The chronology:
- **21 July 2026** — messages during work, `steering` in ACP (MTRH-3031).
- **20 August 2026** — the document on the goal extension (JUNIE-4221), referring to similar implementations in other agents. Note: the contract is described identically in two repositories, which is an attempt at standardization rather than a proprietary protocol.
- **1 October 2026** — the error code `steering_turn_busy` appears in ACP v2 (a commit about the terminal, commands, and prompts).
- **2 November 2026** — commands during work receive the class `SteerableAcpCommand`.

It is clear that the work ran in parallel: the goal contract was described at the same time as it was implemented, and the document records the limits of the implementation (the absence of pause).

## 18.8. What follows

1. **Resolve the race between the end of a turn and a new message inside the agent.** The client must not receive "too late" as an error.
2. **Do not lose messages.** If a message cannot join the current turn, start a new one.
3. **Classify commands by what they do during work.** Some run at once, some extend the task, and some are forbidden.
4. **A goal is session state**, not a single request. The status "active" does not mean "running right now".
5. **Declare only what is implemented.** The list of actions must match the capabilities.
6. **An absent capability and an empty capability are different things.** Do not use `{}` in place of an absent key.
7. **A closing command stops what it promises and nothing else.**

## Exercises

1. Implement an agent that accepts messages during work. If a turn is active, add the message to the current turn; if not, start a new one. Verify that no message is lost in three races: before the start, during the turn, and right after the turn ends.
2. Divide commands into three classes: runs at once, extends the task, forbidden during work. For forbidden commands, return an error code rather than ignoring the command. Verify that `/rollback` is rejected during work.
3. Implement a goal as session state: the command `set` sets the goal, `clear` closes it, and the status `active` persists across prompts. Verify that a new prompt does not reset the goal.
4. Declare capabilities so that an absent capability does not appear in the response at all. Verify that a client without form support does not receive the goal key.

## Sources

All commits cited in this chapter are in the history of `junie-repo` (branch `main`); the text gives their titles and dates. The contracts are `docs/acp-steering.md` and `docs/acp-goal-extension.md`. The classes `Steering.kt` and `SteerableAcpCommand` were checked against HEAD. The number of references to the class (about twenty-two) was obtained through `git grep` in `ej-app`.
