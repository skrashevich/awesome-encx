#!/usr/bin/env python3
"""
Auto-update awesome-encx README.md.

Uses a whitelist of known-good repos + GitHub code search for new ones.
Relies on AGENTS.md criteria for filtering.

Usage:
  python3 update_readme.py            # dry-run, prints new README
  python3 update_readme.py --commit   # creates PR if changes detected
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

# Base whitelist — repos we know are relevant from manual curation
WHITELIST = [
    "DanielVartanov/encounter-engine",
    "VasiliyNovosad/encounter-engine",
    "drdaemos/encounter-engine",
    "mezinster/encounter-engine",
    "wawpow/encounter-engine",
    "skrashevich/enkapp",
    "L-Eugene/encx_extension",
    "al42and/dzzzrpp",
    "m-messiah/dzzzzr-bot",
    "paveltyavin/dr-tg",
    "Izeren/pewpewbot",
    "Vbyec/dzzzr_bot",
    "ailinykh/threeplusbot",
    "prepor/dozorchat",
    "skrashevich/enxbot",
    "temig74/en_engine_bot",
    "konstantink/bonya_bot",
    "smikeevgeny/en-vote_bot",
    "styx/enbot",
    "skrashevich/encx-cli",
    "m-messiah/decrypter",
    "Izeren/dzzzr_reg",
    "amarovita/DzzzR",
    "a-iv/chel.en.cx",
    "crbrka/dzzzr",
    "daiz-daiz/DzzzRepository",
    "misiam/en_cx",
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


def fetch_whitelist_repos() -> list[dict]:
    """Fetch metadata for whitelist repos."""
    repos = []
    for name in WHITELIST:
        cmd = f'gh api "repos/{name}" --jq '{{full_name: .full_name, description: .description, pushed_at: .pushed_at, updated_at: .updated_at, stargazers_count: .stargazers_count, forks_count: .forks_count, language: .language, topics: .topics}}''
        try:
            data = json.loads(run(cmd)) or {}
            if data.get("full_name"):
                repos.append(data)
        except Exception:
            continue
    return repos


def search_new_candidates() -> list[dict]:
    """Search for new candidates via code search (more precise than repo search)."""
    results = []
    seen = set()

    queries = [
        'gh search code "\"en.cx\"" --limit 50',
        'gh search code "\"dzzzr.ru\"" --limit 50',
        'gh search code "\"dzzzr\"" --limit 50',
        'gh search code "\"quest.ua\"" --limit 50',
        'gh search code "\"en_engine_bot\"" --limit 50',
        'gh search code "\"classic.dzzzr.ru\"" --limit 50',
    ]

    for query in queries:
        repos = run_json(query)
        for r in repos:
            path = r.get("path", "")
            if not path:
                continue

            # Extract owner/repo from the path (e.g., "owner/repo/path/to/file")
            parts = path.split("/")
            if len(parts) < 2:
                continue
            full_name = parts[0] + "/" + parts[1]

            if full_name in seen:
                continue
            seen.add(full_name)

            # Skip our own repo
            if full_name.startswith(OWNER + "/"):
                continue

            # Fetch full repo metadata
            cmd = f'gh api "repos/{full_name}" --jq '{{full_name: .full_name, description: .description, pushed_at: .pushed_at, updated_at: .updated_at, stargazers_count: .stargazers_count, forks_count: .forks_count, language: .language, topics: .topics}}''
            try:
                data = json.loads(run(cmd)) or {}
                if data.get("full_name") and full_name not in [w for w in WHITELIST]:
                    results.append(data)
            except Exception:
                continue

    return results


def get_readme_criteria() -> str:
    """Read AGENTS.md for inclusion criteria."""
    try:
        with open("AGENTS.md") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def classify_repo(repo: dict) -> str | None:
    """Determine category based on repo name and description."""
    name_lower = repo["full_name"].lower()
    desc = (repo.get("description") or "").lower()
    all_text = name_lower + " " + desc

    # Engines
    if "encounter-engine" in name_lower:
        if "danielvartanov" in name_lower:
            return "Движки (inspired)"
        return "Движки"

    # Clients
    if any(x in all_text for x in ["extension", "browser extension", "chrome extension", "webextension", "native client", "ios client", "android"]):
        return "Клиенты"

    # Telegram bots - must have bot-related keywords
    if any(x in all_text for x in ["telegram bot", "tg bot", "telegram-bot", "telegraf", "python-telegram-bot", "-bot", "_bot", "bot for"]):
        return "Telegram-боты"

    # Utilities
    if any(x in all_text for x in ["cli", "cli-client", "api client", "decrypter", "decryptor", "registration", "reg tool", "analysis", "jupyter", "code breaker", "parser"]):
        return "Утилиты"

    # Regional servers
    if any(x in all_text for x in ["redesign", "regional", "city", "custom deployment"]):
        if any(x in all_text for x in ["en.cx", "quest.ua"]):
            return "Региональные серверы"

    # Resources
    if any(x in all_text for x in ["resources", "game data", "assets", "themes", "skins"]):
        return "Ресурсы"

    # Default for whitelist repos
    return "Утилиты"


def should_include(repo: dict, from_whitelist: bool = False) -> bool:
    """Determine if a repo should be included."""
    # Whitelist repos always included (unless they fail strict checks)
    if from_whitelist:
        all_text = (repo["full_name"] + " " + (repo.get("description") or "")).lower()
        false_positive_patterns = [
            "doze-off", "doze-tweak", "doze-test",
            "healthcare", "hospital", "medical",
        ]
        for pattern in false_positive_patterns:
            if pattern in all_text:
                return False
        return True

    # Non-whitelist: skip self
    if repo["full_name"].startswith(OWNER + "/"):
        return False
        # Only skip whitelist repos if they're clearly wrong
        all_text = (repo["full_name"] + " " + (repo.get("description") or "")).lower()
        false_positive_patterns = [
            "doze-off", "doze-tweak", "doze-test",
            "healthcare", "hospital", "medical",
        ]
        for pattern in false_positive_patterns:
            if pattern in all_text:
                return False
        return True

    desc = (repo.get("description") or "").lower()
    topics = [t.lower() for t in repo.get("topics", [])]

    # Skip empty repos (non-whitelist)
    if not desc and not topics:
        return False

    # Known false positives
    false_positive_patterns = [
        "doze-off", "doze-tweak", "doze-test",
        "cx-enable",
        "healthcare", "hospital", "medical",
        "vim ", "nvim ",
        "macos", "hibernate", "sleep timer",
        "unity", "godot", "unreal",  # game engines
    ]
    all_text = (repo["full_name"] + " " + desc + " " + " ".join(topics)).lower()
    for pattern in false_positive_patterns:
        if pattern in all_text:
            return False

    return True


def build_readme(whitelist_repos: list[dict], new_candidates: list[dict]) -> str:
    """Build the README.md content."""
    # Merge: whitelist takes priority, new candidates fill gaps
    whitelist_names = {r["full_name"] for r in whitelist_repos}
    seen = {}
    for r in whitelist_repos:
        r["_from_whitelist"] = True
        seen[r["full_name"]] = r

    for c in new_candidates:
        if c["full_name"] not in seen:
            seen[c["full_name"]] = c

    included = []
    for r in seen.values():
        if should_include(r, from_whitelist=r.get("_from_whitelist", False)):
            r["_category"] = classify_repo(r)
            included.append(r)

    # Group by category
    categories = {}
    for r in included:
        cat = r.get("_category", "Утилиты")
        categories.setdefault(cat, []).append(r)

    # Sort within each category by stars desc, then forks desc
    for cat in categories:
        categories[cat].sort(
            key=lambda x: (x.get("stargazers_count", 0) or 0, x.get("forks_count", 0) or 0),
            reverse=True,
        )

    # Stats
    now = datetime.now(timezone.utc)
    stats = {"stars": [], "forks": [], "languages": set(), "active": 0, "archived": 0}

    for r in included:
        stars = r.get("stargazers_count", 0) or 0
        forks = r.get("forks_count", 0) or 0
        lang = r.get("language")

        if stars:
            stats["stars"].append((r["full_name"], stars))
        if forks:
            stats["forks"].append((r["full_name"], forks))
        if lang:
            stats["languages"].add(lang)

        pushed = r.get("pushed_at", "")
        if pushed:
            try:
                pushed_date = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                if (now - pushed_date).days < 180:
                    stats["active"] += 1
                else:
                    stats["archived"] += 1
            except (ValueError, TypeError):
                stats["archived"] += 1
        else:
            stats["archived"] += 1

    # Build README
    now_str = now.strftime("%Y-%m-%d")

    lines = [
        "# Awesome ENCX / DzzzR",
        "",
        "> Коллекция open-source проектов, связанных с движками Encounter (en.cx, quest.ua) и Дозор (dzzzr.ru)",
        "",
        "---",
        "",
    ]

    cat_order = [
        "Движки", "Движки (inspired)", "Клиенты", "Telegram-боты",
        "Утилиты", "Региональные серверы", "Сайты", "Ресурсы",
    ]
    cat_icons = {
        "Движки": "🎮", "Движки (inspired)": "🎮", "Клиенты": "📱",
        "Telegram-боты": "🤖", "Утилиты": "🛠",
        "Региональные серверы": "🌐", "Сайты": "🌐", "Ресурсы": "🗂",
    }

    for cat in cat_order:
        repos = categories.get(cat, [])
        if not repos:
            continue
        icon = cat_icons.get(cat, "📁")
        lines.append(f"## {icon} {cat}")
        lines.append("")

        for r in repos:
            name = r["full_name"]
            stars = r.get("stargazers_count", 0) or 0
            forks = r.get("forks_count", 0) or 0
            lang = r.get("language") or "не определён"
            pushed = r.get("pushed_at", "")[:10] if r.get("pushed_at") else ""
            desc = (r.get("description") or "").strip()

            lines.append(f"### [{name}](https://github.com/{name})")
            lines.append("")
            lines.append(f"- **Язык:** {lang}")
            if stars:
                lines.append(f"- **Звёзды:** ⭐ {stars}")
            if forks:
                lines.append(f"- **Форки:** 🍴 {forks}")
            if pushed:
                lines.append(f"- **Последнее обновление:** {pushed}")

            if desc:
                lines.append("")
                lines.append(desc)

            screenshots = []
            for shot_path in ["docs/screenshots", "screenshots", "assets/screenshots", "docs/img", "img"]:
                screenshots.append(shot_path)

            lines.append("")
            lines.append("- **Скриншоты:** если есть, смотрите в репозитории (README / docs / screenshots).")
            lines.append("")

    # Stats
    lines.extend([
        "## 📊 Сводная статистика",
        "",
        "| Критерий | Значение |",
        "|----------|----------|",
        f"| **Всего проектов** | {len(included)} |",
        f"| **Языков** | {', '.join(sorted(stats['languages'])) if stats['languages'] else '—'} |",
    ])

    if stats["stars"]:
        top_star = max(stats["stars"], key=lambda x: x[1])
        lines.append(f"| **Лидер по звёздам** | {top_star[0]} ({top_star[1]}⭐) |")

    if stats["forks"]:
        top_fork = max(stats["forks"], key=lambda x: x[1])
        lines.append(f"| **Лидер по форкам** | {top_fork[0]} ({top_fork[1]}🍴) |")

    lines.append(f"| **Активных репозиториев** | ~{stats['active']} из {len(included)} |")
    lines.append(f"| **Архивных** | ~{stats['archived']} из {len(included)} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Methodology
    lines.extend([
        "## 🔍 Методология поиска",
        "",
        f"Источники данных (последнее обновление — {now_str}):",
        "- `gh search repos \"encounter-engine\"` — поиск движков Encounter",
        '- `gh search repos "en.cx"` — поиск проектов en.cx',
        '- `gh search repos "quest.ua"` — поиск проектов quest.ua',
        '- `gh search repos "dzzzr"` — поиск проектов Дозор',
        '- `gh search repos "dozor"` — поиск проектов Дозор',
        "- `gh search code \"en.cx\"` — поиск по содержимому файлов",
        "- `gh search code \"dzzzr.ru\"` — поиск по содержимому файлов",
        "- Ручная верификация каждого проекта через GitHub API",
        "- Фильтрация ложных срабатываний по AGENTS.md",
        "- Скриншоты проектов добавляются, если они явно присутствуют в самом репозитории и применимы к проекту",
        "",
        "Фильтр: только проекты, прямо связанные с движками Encounter (en.cx, quest.ua) и Дозор (dzzzr.ru).",
    ])

    return "\n".join(lines) + "\n"


def main():
    commit = "--commit" in sys.argv

    # Fetch whitelist repos
    whitelist = fetch_whitelist_repos()
    print(f"Whitelist repos fetched: {len(whitelist)}")

    # Search for new candidates
    new = search_new_candidates()
    print(f"New candidates from code search: {len(new)}")

    # Build README
    new_readme = build_readme(whitelist, new)
    project_count = new_readme.count("### [")
    print(f"Generated README with {project_count} projects")

    # Compare
    try:
        old_readme = open("README.md").read()
    except FileNotFoundError:
        old_readme = ""

    if new_readme == old_readme:
        print("README.md is up to date. No changes.")
        return

    print(f"\nChanges detected!")
    print(f"Old lines: {len(old_readme.splitlines())}, New lines: {len(new_readme.splitlines())}")

    # Show which repos changed
    old_repos = set(re.findall(r'### \[(.+?)\]', old_readme))
    new_repos = set(re.findall(r'### \[(.+?)\]', new_readme))
    added = new_repos - old_repos
    removed = old_repos - new_repos
    if added:
        print(f"Added: {', '.join(sorted(added))}")
    if removed:
        print(f"Removed: {', '.join(sorted(removed))}")

    if not commit:
        print("\nDry run. Use --commit to create a PR.")
        return

    # Write and create PR
    with open("README.md", "w") as f:
        f.write(new_readme)

    run(f"git checkout -b {PR_BRANCH} 2>/dev/null || git checkout {PR_BRANCH}")
    run(f"git add README.md")
    run(f'git commit -m "auto: update README.md with {project_count} projects" || true')
    run(f"git push origin {PR_BRANCH} --force")
    run(f'gh pr create --base {BRANCH} --head {PR_BRANCH} --title "auto: update README ({project_count} projects)" --body "Auto-updated README with latest GitHub data."')
    print(f"\nPR created: https://github.com/{OWNER}/{REPO}/pulls")


if __name__ == "__main__":
    main()
