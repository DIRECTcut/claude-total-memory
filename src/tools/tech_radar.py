"""
Tech Radar -- monitors new releases of the user's tech stack via GitHub API.

Runs every 12 hours. Checks GitHub releases, summarizes changelogs with Ollama,
saves to memory.db, and sends Telegram notifications.
"""

import json
import os
import re
import sqlite3
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

MEMORY_DIR = Path(os.environ.get("CLAUDE_MEMORY_DIR", os.path.expanduser("~/.claude-memory")))
OLLAMA_BIN = "/usr/local/bin/ollama"
TELEGRAM_ENV_PATH = Path(__file__).parent.parent.parent / "telegram" / ".env"

LOG = lambda msg: sys.stderr.write(f"[tech-radar] {datetime.now().strftime('%H:%M:%S')} {msg}\n")

TECH_STACK_REPOS: list[dict[str, str]] = [
    {"owner": "php", "repo": "php-src", "tech": "PHP"},
    {"owner": "golang", "repo": "go", "tech": "Go"},
    {"owner": "vuejs", "repo": "core", "tech": "Vue"},
    {"owner": "nuxt", "repo": "nuxt", "tech": "Nuxt"},
    {"owner": "postgres", "repo": "postgres", "tech": "PostgreSQL"},
    {"owner": "symfony", "repo": "symfony", "tech": "Symfony"},
    {"owner": "laravel", "repo": "laravel", "tech": "Laravel"},
    {"owner": "redis", "repo": "redis", "tech": "Redis"},
    {"owner": "docker", "repo": "compose", "tech": "Docker Compose"},
]


def _load_dotenv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key:
                result[key] = value
    return result


def _make_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _telegram_send(token: str, chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text[:4096], "parse_mode": parse_mode}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        ctx = _make_ssl_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read()).get("ok", False)
    except Exception as e:
        LOG(f"Telegram send error: {e}")
        return False


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text (terminal colors, cursor moves, etc.)."""
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07", "", text)


def _ollama_generate(prompt: str, model: str = "vitalii-brain", timeout: int = 120) -> str:
    try:
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        result = subprocess.run([OLLAMA_BIN, "run", model, prompt], capture_output=True, text=True, timeout=timeout, env=env)
        return _strip_ansi(result.stdout).strip()
    except subprocess.TimeoutExpired:
        LOG(f"Ollama timeout after {timeout}s")
        return ""
    except FileNotFoundError:
        LOG(f"Ollama binary not found at {OLLAMA_BIN}")
        return ""
    except Exception as e:
        LOG(f"Ollama error: {e}")
        return ""


def _save_knowledge_record(
    db_path: str, content: str, record_type: str = "fact",
    tags: list[str] | None = None, source: str = "auto",
    confidence: float = 0.5, project: str = "general",
) -> None:
    db = sqlite3.connect(db_path)
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute(
            """INSERT INTO knowledge (session_id, type, content, project, tags, source, confidence, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            (f"{source}_{now}_{uuid.uuid4().hex[:6]}", record_type, content, project, json.dumps(tags or []), source, confidence, now),
        )
        db.commit()
    except Exception as e:
        LOG(f"Error saving knowledge ({source}): {e}")
    finally:
        db.close()


def _check_github_release(owner: str, repo: str, state: dict[str, Any], ctx: ssl.SSLContext) -> dict[str, str] | None:
    """Check GitHub for the latest release of a repo."""
    repo_key = f"{owner}/{repo}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "ClaudeMemory-TechRadar/1.0", "Accept": "application/vnd.github+json"})
        gh_token = os.environ.get("GITHUB_TOKEN", "")
        if gh_token:
            req.add_header("Authorization", f"Bearer {gh_token}")
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "")
        if not tag:
            return None
        last_seen_tag = state.get(repo_key, "")
        if tag == last_seen_tag:
            return None
        state[repo_key] = tag
        if not last_seen_tag:
            LOG(f"[{repo_key}] Initial state set: {tag}")
            return None
        return {"tag": tag, "name": data.get("name", tag), "body": data.get("body", "")[:3000], "html_url": data.get("html_url", ""), "prev_tag": last_seen_tag}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _check_github_tag(owner, repo, state, ctx)
        LOG(f"GitHub API error for {repo_key}: {e.code} {e.reason}")
        return None
    except Exception as e:
        LOG(f"GitHub fetch error for {repo_key}: {e}")
        return None


def _check_github_tag(owner: str, repo: str, state: dict[str, Any], ctx: ssl.SSLContext) -> dict[str, str] | None:
    """Fallback: check latest tag via GitHub tags API."""
    repo_key = f"{owner}/{repo}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=1"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "ClaudeMemory-TechRadar/1.0", "Accept": "application/vnd.github+json"})
        gh_token = os.environ.get("GITHUB_TOKEN", "")
        if gh_token:
            req.add_header("Authorization", f"Bearer {gh_token}")
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read())
        if not data or not isinstance(data, list):
            return None
        tag = data[0].get("name", "")
        if not tag:
            return None
        last_seen_tag = state.get(repo_key, "")
        if tag == last_seen_tag:
            return None
        state[repo_key] = tag
        if not last_seen_tag:
            LOG(f"[{repo_key}] Initial tag state set: {tag}")
            return None
        return {"tag": tag, "name": tag, "body": "", "html_url": f"https://github.com/{owner}/{repo}/releases/tag/{tag}", "prev_tag": last_seen_tag}
    except Exception as e:
        LOG(f"GitHub tags fallback error for {repo_key}: {e}")
        return None


def _summarize_changelog(repo_key: str, tag: str, body: str) -> str:
    """Summarize a release changelog using Ollama."""
    if not body or len(body.strip()) < 20:
        return f"New version {tag} released. No detailed changelog available."
    prompt = f"Summarize the key changes in this release of {repo_key} ({tag}) in 2-3 sentences for a developer. Focus on breaking changes, new features, and performance improvements.\n\nChangelog:\n{body[:2500]}"
    summary = _ollama_generate(prompt, timeout=120)
    if not summary:
        for line in body.split("\n"):
            line = line.strip()
            if line and len(line) > 20 and not line.startswith("#"):
                return line[:200]
        return f"New version {tag} released."
    return summary


def _find_affected_projects(db_path: str, tech: str) -> list[str]:
    """Search knowledge DB for projects that mention the given technology."""
    tech_lower = tech.lower()
    try:
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT DISTINCT project FROM knowledge WHERE status = 'active' AND project IS NOT NULL AND project != 'general' AND (LOWER(content) LIKE ? OR LOWER(tags) LIKE ?) ORDER BY project",
            (f"%{tech_lower}%", f"%{tech_lower}%"),
        ).fetchall()
        result = [row["project"] for row in rows]
        db.close()
        return result
    except Exception as e:
        LOG(f"Error searching affected projects for {tech}: {e}")
        return []


def run_tech_radar(db_path: str) -> None:
    """Main Tech Radar function. Checks all tracked repos for new releases."""
    LOG("=== TECH RADAR STARTING ===")
    state_path = MEMORY_DIR / "tech_radar_state.json"
    state: dict[str, Any] = {}
    if state_path.is_file():
        try:
            with open(state_path) as f:
                state = json.load(f)
        except (json.JSONDecodeError, IOError):
            state = {}
    ctx = _make_ssl_context()
    new_releases: list[dict[str, Any]] = []
    for repo_info in TECH_STACK_REPOS:
        owner, repo, tech = repo_info["owner"], repo_info["repo"], repo_info["tech"]
        repo_key = f"{owner}/{repo}"
        LOG(f"Checking {repo_key} ({tech})...")
        release = _check_github_release(owner, repo, state, ctx)
        if release:
            tag = release["tag"]
            LOG(f"New release found: {repo_key} {tag}")
            summary = _summarize_changelog(repo_key, tag, release["body"])
            affected = _find_affected_projects(db_path, tech)
            affected_str = f"\nAffects projects: {', '.join(affected)}" if affected else ""
            content = f"[Tech Radar] {repo_key} released {tag}\nPrevious version: {release.get('prev_tag', '?')}\nURL: {release['html_url']}\n\nSummary: {summary}{affected_str}"
            _save_knowledge_record(db_path, content=content, record_type="fact", tags=["tech-radar", "release", repo, tech.lower()], source="tech-radar", confidence=0.9)
            new_releases.append({"repo_key": repo_key, "tag": tag, "tech": tech, "summary": summary, "affected": affected})
        time.sleep(2)
    try:
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        LOG(f"Error saving tech_radar_state.json: {e}")
    if new_releases:
        env = _load_dotenv(TELEGRAM_ENV_PATH)
        token, allowed = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_ALLOWED_USERS", "")
        if token and allowed:
            for rel in new_releases:
                msg_lines = [f"\U0001f52c <b>Tech Radar: {rel['repo_key']} released {rel['tag']}</b>", "", rel["summary"][:500]]
                if rel["affected"]:
                    msg_lines.extend(["", f"\u26a0\ufe0f Affects: {', '.join(rel['affected'][:5])}"])
                msg = "\n".join(msg_lines)
                for uid in allowed.split(","):
                    uid = uid.strip()
                    if uid:
                        try:
                            _telegram_send(token, int(uid), msg)
                        except ValueError:
                            pass
    LOG(f"=== TECH RADAR COMPLETE === ({len(new_releases)} new releases)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tech Radar")
    parser.add_argument("--db", default=str(MEMORY_DIR / "memory.db"))
    args = parser.parse_args()
    run_tech_radar(args.db)
