# Companion code: a minimal agent

A small Python agent that implements the core ideas of the book in about 250 lines.
It is a teaching tool, not the production agent.

## Run the tests

    cd book-en/companion
    python3 -m unittest discover -s tests -v

Requires Python 3.10 or newer. No third-party packages.

## What is where

| File | What it shows | Chapters |
|---|---|---|
| `minimal_agent/agent.py` `Agent.run` | the loop: ask, parse, execute, observe | 2 |
| `Tools.search_replace` | an edit that refuses ambiguous matches | 8 |
| `Tools.run_command` | a command as a list of arguments, with a timeout | 5, 15 |
| `History` | old observations collapse, long results are cut | 2, 14 |
| `Cache` | responses keyed by a normalized request | 10 |
| `Budget` | a token budget checked at every call | 5, 14 |

## Exercises that use it

- Chapter 2: break the response format on purpose and watch the parser fail.
- Chapter 5: make a command hang, then kill the whole process group.
- Chapter 8: add a rollback that keeps the before and after content of each file.
- Chapter 10: add a check that fails when a prompt change produces a cache miss.
- Chapter 14: add calibration of the token estimate against real usage.

## What it deliberately leaves out

Subagents, sandboxing, the protocol layer, cancellation trees, and model selection.
The book covers those with the real code; this file keeps the loop small enough to read in one sitting.
