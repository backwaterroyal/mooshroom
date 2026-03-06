import json
import re

import click

from mooshroom.config import PROFILES_DIR, PROFILES_FILE

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")


def _load() -> dict:
    if not PROFILES_FILE.exists():
        return {}
    return json.loads(PROFILES_FILE.read_text())


def _save(profiles: dict):
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2))


def list_profiles() -> dict:
    return _load()


def get_profile(name: str) -> dict:
    profiles = _load()
    if name not in profiles:
        raise click.ClickException(f"Profile '{name}' not found.")
    return profiles[name]


def create_profile(
    name: str,
    version: str,
    java_args: str | None = None,
    resolution_width: int | None = None,
    resolution_height: int | None = None,
):
    if not _NAME_RE.match(name):
        raise click.UsageError(
            "Profile name must be 1-50 characters: letters, numbers, hyphens, underscores."
        )
    profiles = _load()
    if name in profiles:
        raise click.ClickException(f"Profile '{name}' already exists.")
    profiles[name] = {
        "version": version,
        "java_args": java_args,
        "resolution_width": resolution_width,
        "resolution_height": resolution_height,
    }
    _save(profiles)


def edit_profile(name: str, **updates):
    profiles = _load()
    if name not in profiles:
        raise click.ClickException(f"Profile '{name}' not found.")
    for key, value in updates.items():
        profiles[name][key] = value
    _save(profiles)


def delete_profile(name: str):
    profiles = _load()
    if name not in profiles:
        raise click.ClickException(f"Profile '{name}' not found.")
    del profiles[name]
    _save(profiles)


def game_dir_for(name: str):
    return PROFILES_DIR / name
