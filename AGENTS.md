# AGENTS — Criteria for awesome-encx

Rules for curating projects in `awesome-encx/README.md`.
Follow these to avoid common mistakes.

## Inclusion criteria

A repository **may** be included only if it has **direct, explicit connection**
to one of:

- **Encounter** engine / platform — `en.cx`, `quest.ua`, `encounter-engine`
- **DzzzR / DozoR** engine / platform — `dzzzr.ru`, `classic.dzzzr.ru`
- Software that **directly interacts** with these platforms (bots, clients,
  CLI tools, extensions, scrapers, decrypters, server instances)

## Exclusion criteria

A repository **must NOT** be included if:

1. **Name match only.** The repo name contains `dzzzr`, `dozor`, `encounter`,
   or `en.cx` but the actual content is unrelated
   (e.g. a default GitHub Pages "Hello World" page).
   **Always verify by reading the repo description and listing contents.**

2. **Generic engine, not platform-specific.** A repo is a standalone game engine
   that happens to be "similar" to en.cx — but is not an engine, fork, client
   or extension for en.cx / dzzzr.
   Example: `DanielVartanov/encounter-engine` is a generic urban quest engine
   *inspired by* en.cx, not an engine *of* en.cx.
   Such repos may be listed in a separate "inspired by" section, but never
   mixed into engine/client/tool categories.

3. **No verifiable link.** You cannot confirm the project targets encounter/dzzzr
   through repo description, code, topics, or README.

## Description rules

- **Never** claim a project is "actively developed", "actively maintained" or
  "активно развивается" unless the last **push** date is within the last 6
  months.
- **Always** distinguish between `pushed_at` (real code activity) and
  `updated_at` (metadata/comments). Use `pushed_at` from the GitHub API.
- **Never** describe a repo based on its name alone. Read the actual
  `description` field from the GitHub API.
- For forks, name the upstream repo explicitly (e.g. "Fork of X").
- For deprecated/abandoned repos, state when activity stopped.

## Data source rules

- Always fetch metadata via `gh api repos/<owner>/<repo>` — do not rely on
  search snippet descriptions; they can be misleading.
- When in doubt, list the repo contents: `gh api repos/<owner>/<repo>/contents`
  to confirm relevance.
- Remove repos that turn out to be false positives after verification.

## Category definitions

| Category | What goes here |
|---|---|
| Движки | The actual game engines (origin and significant forks) |
| Клиенты | Browser extensions, mobile apps, desktop clients |
| Telegram-боты | Bots that interact with encounter/dzzzr platforms |
| Утилиты | CLI tools, decrypters, registration helpers, data analysis |
| Региональные серверы | Custom deployments of the engine for specific cities/regions |
| Сайты | Official or community websites (not generic hosting pages) |
| Ресурсы | Code snippets, game data, assets for dzzzr/en.cx |

## Update procedure

1. Run search queries with new keywords.
2. For each candidate repo, fetch metadata via GitHub API.
3. Verify relevance by reading the description and listing contents.
4. Cross-check against existing entries to avoid duplicates.
5. Update `README.md` following the rules above.
6. Run `grep "^### \[" README.md | wc -l` to confirm total count matches
   the stats table.
7. Push to `main`.
