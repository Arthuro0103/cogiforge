# Bring your chat history into the vault

Your past chats with Claude, ChatGPT or Gemini hold years of your own thinking. This guide shows how to
export them from the site and turn them into notes the vault can use.

> **Websites change.** Menu names and export contents below were checked on **2026-10-07** against the
> vendors' own help pages (support.claude.com, help.openai.com, support.google.com). Anything I could
> not confirm there is marked `[VERIFY: ...]`: try it, and if the site differs, trust the site and fix
> this file. Never assume a step still exists.

## Read this first: privacy

- **An export contains everything you ever said in those chats**, including things you forgot you
  typed: names, health, money, other people's data, passwords pasted by mistake.
- **Nothing is cleaned for you.** Import into `vault/inbox/chats/` (not into `notes/`), read what came
  in, and delete what should not be kept.
- **Run `python3 core/leak.py .` before every commit** that carries imported text. It catches machine
  paths, e-mails, phone numbers and tax ids, plus a private list of terms you keep outside the repo. It
  does not catch everything a person would call private.
- **A shared repository means everyone reads it.** In a group or a school repo, whatever you commit is
  visible to every member, forever (git history). Keep personal chats out: add `vault/inbox/chats/` to
  your own `.gitignore` or to `.git/info/exclude`, and promote only what you wrote into a note on purpose.
- The download link goes to your e-mail and expires; do not forward it.

## The four kinds of data

| Data | What it is | Claude | ChatGPT | Gemini |
|---|---|---|---|---|
| Conversations | the chats themselves | in the export | in the export | in "My Activity" |
| Projects | a workspace with instructions and files | `[VERIFY: whether projects are in the Claude export; only third-party pages say so, checked 2026-10-07]` | `[VERIFY: whether ChatGPT Projects are in the export; not stated on the help page, checked 2026-10-07]` | not applicable |
| Memory | what the assistant remembers about you | separate route, see below | `[VERIFY: whether memory is in the ChatGPT export; not stated on the help page, checked 2026-10-07]` | not applicable |
| Attached files | what you uploaded | `[VERIFY: whether attachments are exported; third-party pages say file contents are not, checked 2026-10-07]` | `[VERIFY: whether uploaded files and images are in the zip; not stated on the help page, checked 2026-10-07]` | uploads are listed as included in the Gemini Apps activity |

`tools/import_chats.py` reads **conversations only**. It lists attachment file names, never their
contents. Projects, memory and files you handle by hand (see the end of this guide).

## Claude (claude.ai)

Source: [Export your Claude data](https://support.claude.com/en/articles/9450526-export-your-claude-data).

1. Open claude.ai in a browser, or Claude Desktop. The help page says the export is **not** available
   in the iOS or Android app.
2. Click your **initials** in the lower left corner.
3. Choose **Settings**, then the **Privacy** section.
4. Click **Export data**.
5. Wait for an e-mail to the address on your account. It carries a download link. You must be signed
   in to your account to use it.
6. Download the zip before the link expires: **24 hours** after delivery. If it expires, repeat the
   export to get a new link.

Limits and conditions from the same page:

- Individual accounts (Free, Pro, Max) can export. On a Team or Enterprise plan, only the
  organization's **Primary Owner** can access data exports.
- The export "includes conversation data and the user data for your account." The page does not
  describe the file names inside the zip or give a size limit:
  `[VERIFY: file names inside the Claude zip (expected conversations.json); not in the official page, checked 2026-10-07]`
  `[VERIFY: maximum size or splitting of the Claude zip; not in the official page, checked 2026-10-07]`
- Exported data cannot be imported into another personal Claude account.

**Memory.** Claude's memory has its own official route: see
[Import and export your memory from Claude](https://support.claude.com/en/articles/12123587). It says to
go to Settings and ask Claude to "Write out your memories of me verbatim, exactly as they appear in your
memory." Save the answer as a text file.
`[VERIFY: the exact Settings menu path for memory; the page only says "Settings", checked 2026-10-07]`

## ChatGPT

Source: [How do I export my ChatGPT history and data](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data)
(the page returned an error to my automated fetch; the steps below come from the search summary of that
same page, so confirm them on screen).

1. Sign in to ChatGPT and open your **profile menu**.
2. Choose **Settings**, then **Data controls**.
3. Under **Export data**, click **Export**, then **Confirm export** on the confirmation screen.
4. ChatGPT sends an **e-mail or SMS** when it is ready. It can take **up to 7 days**.
5. Open the message and click **Download data export**. The link expires **24 hours** after you
   receive it. The download is a **ZIP** with your chat history and other account data.

Conditions: available for Free, Plus, Pro and eligible Edu workspaces; **not** available for Business
or Enterprise workspaces. There is also a second route through OpenAI's Privacy Portal ("Download my
data").
`[VERIFY: ChatGPT zip contents; people report conversations.json and chat.html, but the help page text I could read did not name them, checked 2026-10-07]`
`[VERIFY: whether a big history is split into several conversations-NNN.json files; the importer accepts them, but I have not confirmed OpenAI does this, checked 2026-10-07]`

## Gemini (Google Takeout)

Source: [Download your Gemini Apps data](https://support.google.com/gemini/answer/16920332).

1. Go to takeout.google.com and sign in to **the same Google Account you use for Gemini Apps**.
2. Click **Deselect all**.
3. For your chats, check **My Activity**, then open **All activity data included**, click **Deselect all**,
   check **Gemini Apps**, and click **OK**. (Checking only the top-level **Gemini** box covers Gems
   data, not your chats.)
4. Choose the delivery method (e-mail link, Google Drive, Dropbox, OneDrive or Box) and the archive
   type, **.zip** or **.tgz**, then create the export. An e-mail link works for 7 days.

The export "contains your Gemini chats, generated media, and uploads". Downloading it does not delete
anything from Google.

- `[VERIFY: whether the Gemini activity comes as HTML or JSON, and its structure; the official page does not say, checked 2026-10-07]`
- `[VERIFY: whether Google Workspace (school or company) accounts can export Gemini activity; the page I read does not address it, checked 2026-10-07]`
- **`tools/import_chats.py` does not read Gemini archives.** Put the files as they come in
  `vault/inbox/gemini/` and process them by hand with a target, as for any inbox item.

## Bring it into the vault

Unzip nothing: the importer reads the zip directly.

```sh
python3 tools/import_chats.py ~/Downloads/<your-export>.zip --dry-run   # report only, writes nothing
python3 tools/import_chats.py ~/Downloads/<your-export>.zip             # one .md per conversation
python3 core/leak.py .                                                 # before any commit
```

- It also accepts a plain `conversations.json`. It detects the format by structure: ChatGPT keeps each
  chat as a tree and the importer follows the branch you actually see (abandoned branches are left
  out); claude.ai keeps a flat list of messages.
- Output goes to `vault/inbox/chats/` (change it with `--dest`). Each file has `type: chat`,
  `source: claude|chatgpt`, `date`, `title`, and separate `## User` and `## Assistant` turns, so what
  *you* said is never mixed with what the model said. Only the first is evidence about you.
- Empty conversations are reported and skipped. Existing files are never overwritten, so a second
  run is safe.
- Exit codes: `0` all written · `1` some conversations skipped (the report says why) · `2` usage ·
  `3` unreadable file or **format not recognized**.

## What to do after importing

An imported chat is raw material. Per the vault rules, it is processed only when a file that already
existed changes: pick a target (`project::`, `article::`, `question::`, `task::` or `none`) and move
only what matters. In a chat, the model's words are context, not facts about you: nothing goes into
`vault/memory/profile.md` unless you say it is yours and it carries your quote.

Projects, memory and attached files are not converted. Save the memory text as a note in `inbox/`
and decide its target. Re-download attached files from the project pages you still have.
