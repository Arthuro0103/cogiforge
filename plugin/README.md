# Cogiforge plugin for Claude Code

This plugin gives Claude Code two skills for Cogiforge, a second-brain workbench in Obsidian for coding agents, with a commit gate that checks the agent's memory.

- `/cf-new-workbench` asks for a folder and builds a new workbench there, with the commit gate turned on and a first commit.
- `/cf-adopt` puts the commit gate on an Obsidian vault you already have, in place. It shows the plan first and applies it only after your yes.

## Install

In a terminal:

```sh
claude plugin install cogiforge --marketplace Arthuro0103/cogiforge
```

## Why only two skills

The repo has 18 skills. They live inside each workbench, and Claude Code loads only the skills of the folder it is opened in, so they appear where they work. The git hook also needs a fixed path, which a plugin folder cannot give.

## Why the plugin is only Markdown

The Anthropic plugin directory accepts code only from a verified organization. So this plugin carries instructions and no scripts: the skills download the workbench from this repo on GitHub at a fixed version, by commit hash, and check the hash before running anything: plugin 0.1.3 installs Cogiforge 0.1.2 (commit `74177d4`). To ship a new Cogiforge version, tag it first; then a following commit of the plugin pins that tag's hash and raises the plugin version. It needs `git` and an internet connection.

More in the repo README: https://github.com/Arthuro0103/cogiforge#readme
