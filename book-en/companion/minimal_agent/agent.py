"""A minimal agent loop: the teaching companion for the book.

It implements the ideas of Chapters 2, 5, 8, 10, and 14 in roughly 250 lines:
an action loop, four actions, a history that collapses old observations,
an edit that refuses ambiguous matches, a cache of model responses keyed by a
normalized request, a token budget, and a command runner with a hard timeout.

It is deliberately small. It is not the production agent.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

KEEP_TAIL = 10                  # observations kept in full (Chapter 14)
MAX_KEPT_RESULT_CHARS = 2_000   # longer results are cut to a head (Chapter 14)
RESULT_HEAD_CHARS = 1_000
CHARS_PER_TOKEN = 3             # the initial token estimate (Chapter 14)
UNSTABLE = [                    # what changes between runs and must not affect the key
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"), "<time>"),
    (re.compile(r"/tmp/[A-Za-z0-9_\-]+"), "<tmp>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<addr>"),
]


class ActionError(Exception):
    """An action was refused. The message goes back to the model as an observation."""


class BudgetExceeded(Exception):
    pass


class Model(Protocol):
    def complete(self, prompt: str) -> str: ...


class Tools:
    """The four actions. Every path is resolved inside the project root."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, relative: str) -> Path:
        target = (self.root / relative).resolve()
        if self.root not in target.parents and target != self.root:
            raise ActionError(f"path escapes the project: {relative}")
        return target

    def read_file(self, path: str) -> str:
        return self._path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {path}"

    def search_replace(self, path: str, search: str, replace: str, replace_all: bool = False) -> str:
        target = self._path(path)
        text = target.read_text(encoding="utf-8")
        count = text.count(search)
        if count == 0:
            raise ActionError("search text not found; include more exact context")
        if count > 1 and not replace_all:
            # Refusing is safer than guessing which occurrence was meant (Chapter 8).
            raise ActionError(f"search text matches {count} times; make it unique or set replace_all")
        target.write_text(text.replace(search, replace), encoding="utf-8")
        return f"replaced {count} occurrence(s) in {path}"

    def run_command(self, argv: list[str], timeout: float = 30.0) -> str:
        # A list, not a string: no shell interprets the arguments (Chapter 15).
        try:
            done = subprocess.run(
                argv, cwd=self.root, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            # subprocess.run kills the child on timeout; a real runner must also kill its group.
            raise ActionError(f"command timed out after {timeout}s") from exc
        return f"exit={done.returncode}\n{done.stdout}{done.stderr}"


@dataclass
class History:
    """Observations. Old ones are collapsed; long results are cut (Chapter 14)."""

    items: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        if len(text) > MAX_KEPT_RESULT_CHARS:
            text = text[:RESULT_HEAD_CHARS] + f"\n[... {len(text) - RESULT_HEAD_CHARS} chars cut ...]"
        self.items.append(text)

    def render(self) -> str:
        old, recent = self.items[:-KEEP_TAIL], self.items[-KEEP_TAIL:]
        collapsed = [f"[collapsed observation of {len(item)} chars]" for item in old]
        return "\n".join(collapsed + recent)


class Cache:
    """Responses keyed by the normalized request (Chapter 10)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.misses = 0

    @staticmethod
    def key(prompt: str) -> str:
        normalized = prompt
        for pattern, replacement in UNSTABLE:
            normalized = pattern.sub(replacement, normalized)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get_or_call(self, model: Model, prompt: str) -> str:
        key = self.key(prompt)
        if key not in self.store:
            self.misses += 1
            self.store[key] = model.complete(prompt)
        return self.store[key]


@dataclass
class Budget:
    limit_tokens: int
    spent_tokens: int = 0

    def charge(self, text: str) -> None:
        self.spent_tokens += max(1, len(text) // CHARS_PER_TOKEN)
        if self.spent_tokens > self.limit_tokens:
            raise BudgetExceeded(f"spent {self.spent_tokens} of {self.limit_tokens} tokens")


class Agent:
    """The loop of Chapter 2: ask, parse, execute, observe, repeat."""

    def __init__(self, model: Model, tools: Tools, budget: Budget, cache: Cache | None = None):
        self.model = model
        self.tools = tools
        self.budget = budget
        self.cache = cache or Cache()
        self.history = History()

    def run(self, task: str, max_steps: int = 40) -> str:
        for _ in range(max_steps):
            prompt = f"TASK: {task}\nHISTORY:\n{self.history.render()}\nRespond with one JSON action."
            self.budget.charge(prompt)
            reply = self.cache.get_or_call(self.model, prompt)
            self.budget.charge(reply)
            try:
                action = json.loads(reply)
                name, args = action["action"], action.get("args", {})
            except (ValueError, KeyError, TypeError):
                self.history.add("error: response is not a JSON action")
                continue
            if name == "finish":
                return str(args.get("summary", ""))
            self.history.add(self._execute(name, args))
        raise RuntimeError("step limit reached")

    def _execute(self, name: str, args: dict) -> str:
        actions = {
            "read_file": self.tools.read_file,
            "write_file": self.tools.write_file,
            "search_replace": self.tools.search_replace,
            "run_command": self.tools.run_command,
        }
        if name not in actions:
            return f"error: unknown action {name}"
        try:
            return str(actions[name](**args))
        except ActionError as error:
            return f"error: {error}"
        except OSError as error:
            # A missing file is an observation for the model, not a crash of the loop.
            return f"error: {error.strerror or error}"
        except TypeError as error:
            return f"error: bad arguments for {name}: {error}"
