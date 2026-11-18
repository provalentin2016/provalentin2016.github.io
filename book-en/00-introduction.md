# Introduction

[Contents](README.md) · [Next →](01-from-prd-to-app.md)

This book is about building an AI agent that writes and changes code. It is not a tutorial written from a blank page. It is a reconstruction of how one real agent was built, from the first commit in March 2024 to the state of the repository in November 2026, using only what the repository itself records.

The project began as an internal IntelliJ plugin called Matterhorn. Its job was to take a product description and generate a working application. Over two and a half years it grew into Junie: an agent that works in the IDE, in the terminal, in editors that speak the Agent Client Protocol, and in a Slack bot used by a team. The repository holds about 15,900 commits from more than two hundred authors. Almost all of the design decisions, the failures, and the reversals are visible in its history, often in commit titles and in the design documents that the team kept next to the code.

## Who this book is for

The book is for engineers who want to build an agent that does real work, not a demonstration that answers one question. It assumes you can read Kotlin or a similar language, know what a git history is, and have run a language model through an API. It does not assume you have built an agent before. Where a concept is specific to this project, the chapter introduces it.

It is also written for people who will maintain an agent over years. Most of the hard problems in this history are not about getting the model to answer. They are about what happens after the answer: how a failed edit is undone, how a cancelled task releases its processes, how a second client gets the same behavior as the first, how a name can be changed without breaking the files of a user who installed the product last year.

## How the book was written

Every claim in the book is traced to something in the repository. Commit titles and dates come from the history. Class names, file paths, and constants were checked against the current code, or against the historical version where the code has since been removed. Where a reason is not recorded anywhere, the chapter says so instead of guessing. A number of conclusions are marked as inferences, for example when they come from a commit title and not from the diff.

Three limits follow from this method, and they matter for how you read the book.

First, the history does not contain everything. There are no accuracy metrics for the early HumanEval experiments, so the book gives no solve rates. Many decisions were made in discussions that are not in the repository, and the book describes only what the repository shows.

Second, parts of the system have been removed. The generator line (webgen, Kineto) and its recipe catalog were deleted from the current code in November 2025. Chapters 1 through 5 describe that line in detail, and each one says what survived. Ideas are often more durable than the code that carried them.

Third, one part is not in the repository at all. The server side of Junie Live is not in this repository. Chapter 19 is therefore based on the design document and on the configuration of the agent that serves the Slack bot.

## How to read the book

The chapters follow the history. Part I covers the Matterhorn prototype: a generation pipeline, the first agent loop, parallel runs, a knowledge catalog, and reliability. Part II covers the IDE agent: the module split, the execution context, tools and edits, subagents, testing, and naming. Part III covers the move from the IDE to the terminal: the standalone application, MCP, context management, the sandbox, and multiple models. Part IV covers protocols, services, and the team process.

Each chapter has the same shape. It starts with a problem, shows what the team tried and in what order, presents the code or the document that resolved it, and ends with the lessons and exercises. A section called "What became of it in the current code" tells you what still exists. The exercises are meant to be done. Some of them assume a companion implementation, described in the next section.

The glossary and the timeline at the end are reference material. Use them when a term or a date is unfamiliar.

## The companion code

A book about building an agent should let you build one. The companion code in the `companion/` folder is a small agent that implements the core ideas of the first chapters: a loop, a fixed set of actions, a history with compression, an edit that refuses ambiguous matches, a cache of model responses, and a budget. It is deliberately much smaller than the real agent. The exercises in Chapters 2, 5, 8, 10, and 14 can be done on top of it.

## A note on names

The book uses the names the team used at the time. Matterhorn is the internal name of the early product, and Junie is the public name. Commit titles are quoted as they were written, including their spelling. Internal ticket numbers have been removed, because they are not meaningful outside the team.

Let us begin with the first commit, and with the first problem: how to turn a product description into a project that compiles.
