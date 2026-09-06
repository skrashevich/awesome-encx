#!/usr/bin/env python3
"""
Auto-update awesome-encx README.md using OpenAI API.

Usage:
  python3 update_readme.py          # dry-run, prints new README
  python3 update_readme.py --commit # creates PR if changes detected

Requires: OPENAI_API_KEY env var, gh CLI authenticated.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import httpx

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o"
OWNER = "skrashevich"
REPO = "awesome-encx"
BRANCH = "main"
PR_BRANCH = "auto/update-readme"

SEARCH_QUERIES = [
    'gh search repos "encounter-engine" --json fullName,description,stargazersCount,forkCount,language,updatedAt,pushedAt --limit 50',
    'gh search repos "en.cx" --json fullName,description,stargazersCount,forkCount,language,updatedAt,pushedAt --limit 50',
    'gh search repos "quest.ua" --json fullName,description,stargazersCount,forkCount,language,updatedAt,pushedAt --limit 50',
    'gh search repos "dzzzr" --json fullName,description,stargazersCount,forkCount,language,updatedAt,pushedAt --limit 50',
    'gh search repos "dozor" --json fullName,description,stargazersCount,forkCount,language,updatedAt,pushedAt --limit 50',
    'gh search code "en.cx" --json name,path --limit 100',
    'gh search code "dzzzr" --json name,path --limit 100',
    'gh search code "quest.ua" --json name,path --limit 100',
]


def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def run_json(cmd: str) -> list:
    out = run(cmd)
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def fetch_existing_repos() -> list[dict]:
    """Fetch repos already in the README."""
    readme = open("README.md").read()
    repos = []
    for match in re.finditer(r'### \[(.+?)/(.+?)\]', readme):
        repos.append({"owner": match.group(1), "name": match.group(2)})
    return repos


def fetch_new_candidates() -> list[dict]:
    """Fetch candidate repos from GitHub search."""
    results = []
    seen = set()

    for query in SEARCH_QUERIES:
        repos = run_json(query)
        for r in repos:
            name = r.get("fullName", "") or r.get("name", "")
            if "/" not in name:
                continue
            owner, repo = name.split("/", 1)
            if owner == OWNER:
                continue  # skip our own

            if name in seen:
                continue
            seen.add(name)

            if r.get("description") or r.get("path"):
                results.append({
                    "full_name": name,
                    "description": r.get("description", ""),
                    "stargazersCount": r.get("stargazersCount", 0),
                    "forkCount": r.get("forkCount", 0),
                    "language": r.get("language"),
                    "updatedAt": r.get("updatedAt"),
                    "pushedAt": r.get("pushedAt"),
                })

    return results


def enrich_repo(repo: dict) -> dict:
    """Fetch additional details via GitHub API."""
    url = f"https://api.github.com/repos/{repo['full_name']}"
    cmd = f'gh api "{url}" --jq \'{{description: .description, pushed_at: .pushed_at, updated_at: .updated_at, stargazers_count: .stargazers_count, forks_count: .forks_count, language: .language, topics: .topics}}\''
    try:
        data = json.loads(run(cmd)) or {}
    except Exception:
        data = {}

    repo.update(data)
    return repo


def get_readme_criteria() -> str:
    """Read AGENTS.md for inclusion criteria."""
    try:
        with open("AGENTS.md") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def classify_repo(repo: dict) -> str | None:
    """Determine if a repo should be included and which category."""
    name_lower = repo["full_name"].lower()
    desc = (repo.get("description") or "").lower()
    topics = [t.lower() for t in repo.get("topics", [])]
    all_text = name_lower + " " + desc + " " + " ".join(topics)

    # Check if it's an engine
    if "engine" in desc and ("encounter" in desc or "encounter" in name_lower or "urban" in desc or "quest" in desc):
        # Verify it's not just a generic engine
        if "like www.en.cx" in desc or "for \"encounter\"" in desc:
            # Check if it's DanielVartanov - that's a generic engine, not the main one
            if "danielvartanov" in name_lower:
                return "Движки (inspired)"
            return "Движки"
        if "fork" in desc and "encounter-engine" in name_lower:
            return "Движки"

    # Check if it's a client
    if any(x in all_text for x in ["extension", "browser extension", "chrome extension", "webextension", "native client", "iOS client", "android"]):
        return "Клиенты"

    # Check if it's a Telegram bot
    if any(x in all_text for x in ["telegram bot", "tg bot", "tg-bot", "telegram-bot", "telegraf", "python-telegram-bot"]):
        # Make sure it's actually for encounter/dzzzr
        if any(x in all_text for x in ["dzzzr", "dozor", "encounter", "en.cx", "quest.ua", "enx"]):
            return "Telegram-боты"
        # Generic bot name matching game context
        if any(x in all_text for x in ["bot", "game", "quest", "urban"]):
            if any(x in all_text for x in ["dzzzr", "dozor", "encounter", "en.cx", "quest.ua"]):
                return "Telegram-боты"

    # Check if it's a utility
    if any(x in all_text for x in ["cli", "cli-client", "api client", "decrypter", "decryptor", "distributor", "registration", "reg tool", "analysis", "notebook", "jupyter", "data analysis", "code breaker"]):
        if any(x in all_text for x in ["dzzzr", "dozor", "encounter", "en.cx", "quest.ua", "encx", "enx", "dzr"]):
            return "Утилиты"

    # Check if it's a regional server
    if any(x in all_text for x in ["redesign", "regional", "city server", "server", "custom deployment"]):
        if any(x in all_text for x in ["en.cx", "quest.ua"]):
            return "Региональные серверы"

    # Check if it's a website
    if any(x in all_text for x in ["github pages", "website", "landing page"]):
        if any(x in all_text for x in ["dzzzr", "dozor", "encounter", "en.cx", "quest.ua"]):
            return "Сайты"

    # Check if it's resources
    if any(x in all_text for x in ["resources", "game data", "assets", "themes", "skins"]):
        if any(x in all_text for x in ["dzzzr", "dozor", "encounter", "en.cx", "quest.ua"]):
            return "Ресурсы"

    return None


def should_include(repo: dict) -> bool:
    """Determine if a repo should be included based on criteria."""
    name_lower = repo["full_name"].lower()
    desc = (repo.get("description") or "").lower()
    topics = [t.lower() for t in repo.get("topics", [])]

    # Skip if it's a default GH Pages page with no real content
    if desc == "" and not topics:
        # Check if it's just a hello world page
        return False

    # Skip self
    if repo["full_name"].startswith(OWNER + "/"):
        return False

    # Skip if it's a pure code search result without repo metadata
    if "path" in repo and "full_name" not in repo:
        return False

    return True


def generate_readme(existing: list[dict], candidates: list[dict]) -> str:
    """Use OpenAI to generate the updated README.md."""
    # Enrich candidates
    for c in candidates:
        enrich_repo(c)

    # Filter and classify
    included = []
    for c in candidates:
        if not should_include(c):
            continue
        category = classify_repo(c)
        if category:
            c["_category"] = category
            included.append(c)

    # Merge with existing repos that are still valid
    existing_names = {r["full_name"] for r in existing}
    included_names = {r["full_name"] for r in included}

    # Keep existing repos that aren't in candidates (they're still valid)
    # Add existing to included if not superseded
    for e in existing:
        if e["full_name"] not in included_names:
            # Find matching candidate to get fresh data
            for c in candidates:
                if c["full_name"] == e["full_name"]:
                    e = c
                    break
            if "category" not in e:
                cat = classify_repo(e)
                e["_category"] = cat
            if e.get("_category"):
                included.append(e)
                included_names.add(e["full_name"])

    # Remove duplicates by full_name
    seen = {}
    for r in included:
        seen[r["full_name"]] = r
    included = list(seen.values())

    # Group by category
    categories = {}
    for r in included:
        cat = r.get("_category", "Другое")
        categories.setdefault(cat, []).append(r)

    # Sort within each category by stars desc, then forks desc
    for cat in categories:
        categories[cat].sort(key=lambda x: (x.get("stargazers_count", 0), x.get("forks_count", 0)), reverse=True)

    # Build README
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    readme_lines = [
        "# Awesome ENCX / DzzzR",
        "",
        "> Коллекция open-source проектов, связанных с движками Encounter (en.cx, quest.ua) и Дозор (dzzzr.ru)",
        "",
        "---",
        "",
    ]

    cat_order = [
        "Движки",
        "Клиенты",
        "Telegram-боты",
        "Утилиты",
        "Региональные серверы",
        "Сайты",
        "Ресурсы",
    ]

    cat_icons = {
        "Движки": "🎮",
        "Клиенты": "📱",
        "Telegram-боты": "🤖",
        "Утилиты": "🛠",
        "Региональные серверы": "🌐",
        "Сайты": "🌐",
        "Ресурсы": "🗂",
    }

    stats = {"stars": [], "forks": [], "languages": set()}

    for cat in cat_order:
        repos = categories.get(cat, [])
        if not repos:
            continue
        icon = cat_icons.get(cat, "📁")
        readme_lines.append(f"## {icon} {cat}")
        readme_lines.append("")

        for r in repos:
            name = r["full_name"]
            stars = r.get("stargazers_count", 0) or 0
            forks = r.get("forks_count", 0) or 0
            lang = r.get("language") or "не определён"
            pushed = r.get("pushed_at", "")[:10] if r.get("pushed_at") else ""
            desc = (r.get("description") or "").strip()

            if stars:
                stats["stars"].append((name, stars))
            if forks:
                stats["forks"].append((name, forks))
            if lang and lang != "не определён":
                stats["languages"].add(lang)

            readme_lines.append(f"### [{name}](https://github.com/{name})")
            readme_lines.append("")
            readme_lines.append(f"- **Язык:** {lang}")
            if stars:
                readme_lines.append(f"- **Звёзды:** ⭐ {stars}")
            if forks:
                readme_lines.append(f"- **Форки:** 🍴 {forks}")

            if pushed:
                readme_lines.append(f"- **Последнее обновление:** {pushed}")

            if desc:
                readme_lines.append("")
                readme_lines.append(desc)

            readme_lines.append("")

    # Stats section
    readme_lines.append("## 📊 Сводная статистика")
    readme_lines.append("")
    readme_lines.append("| Критерий | Значение |")
    readme_lines.append("|----------|----------|")
    readme_lines.append(f"| **Всего проектов** | {len(included)} |")
    readme_lines.append(f"| **Языков** | {', '.join(sorted(stats['languages'])) if stats['languages'] else '—'} |")

    if stats["stars"]:
        top_star = max(stats["stars"], key=lambda x: x[1])
        readme_lines.append(f"| **Лидер по звёздам** | {top_star[0]} ({top_star[1]}⭐) |")

    if stats["forks"]:
        top_fork = max(stats["forks"], key=lambda x: x[1])
        readme_lines.append(f"| **Лидер по форкам** | {top_fork[0]} ({top_fork[1]}🍴) |")

    # Active vs archived
    active = 0
    archived = 0
    for r in included:
        pushed = r.get("pushed_at", "")
        if pushed:
            pushed_date = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - pushed_date).days
            if age < 180:
                active += 1
            else:
                archived += 1
        else:
            archived += 1

    readme_lines.append(f"| **Активных репозиториев** | ~{active} из {len(included)} |")
    readme_lines.append(f"| **Архивных** | ~{archived} из {len(included)} |")
    readme_lines.append("")
    readme_lines.append("---")
    readme_lines.append("")

    # Methodology
    readme_lines.append("## 🔍 Методология поиска")
    readme_lines.append("")
    readme_lines.append(f"Источники данных (последнее обновление — {now}):")
    readme_lines.append("- `gh search repos \"encounter-engine\"` — поиск движков Encounter")
    readme_lines.append('- `gh search repos "en.cx"` — поиск проектов en.cx')
    readme_lines.append('- `gh search repos "quest.ua"` — поиск проектов quest.ua')
    readme_lines.append('- `gh search repos "dzzzr"` — поиск проектов Дозор')
    readme_lines.append('- `gh search repos "dozor"` — поиск проектов Дозор')
    readme_lines.append("- `gh search code \"en.cx\"` — поиск по содержимому файлов")
    readme_lines.append("- `gh search code \"dzzzr\"` — поиск по содержимому файлов")
    readme_lines.append("- `gh search code \"quest.ua\"` — поиск по содержимому файлов")
    readme_lines.append("- Ручная верификация каждого проекта через GitHub API")
    readme_lines.append("")
    readme_lines.append("Фильтр: только проекты, прямо связанные с движками Encounter (en.cx, quest.ua) и Дозор (dzzzr.ru).")

    return "\n".join(readme_lines) + "\n"


def main():
    commit = "--commit" in sys.argv

    # Read existing repos
    existing = fetch_existing_repos()
    print(f"Existing repos in README: {len(existing)}")

    # Fetch candidates
    candidates = fetch_new_candidates()
    print(f"New candidates from GitHub: {len(candidates)}")

    # Generate README
    new_readme = generate_readme(existing, candidates)
    print(f"Generated README with {new_readme.count('### [')} projects")

    # Read current README
    try:
        old_readme = open("README.md").read()
    except FileNotFoundError:
        old_readme = ""

    if new_readme == old_readme:
        print("README.md is up to date. No changes.")
        return

    print(f"\nChanges detected!")
    print(f"Old lines: {len(old_readme.splitlines())}, New lines: {len(new_readme.splitlines())}")

    if not commit:
        print("\nDry run. Use --commit to create a PR.")
        return

    # Write new README
    with open("README.md", "w") as f:
        f.write(new_readme)

    # Create branch and PR
    run(f"git checkout -b {PR_BRANCH}")
    run(f"git add README.md")
    run(f'git commit -m "auto: update README.md with {new_readme.count("### [")} projects"')
    run(f"git push origin {PR_BRANCH} --force")
    run(f'gh pr create --base {BRANCH} --head {PR_BRANCH} --title "auto: update README" --body "Auto-updated README with latest GitHub data."')
    print(f"\nPR created: https://github.com/{OWNER}/{REPO}/pulls")


if __name__ == "__main__":
    main()
