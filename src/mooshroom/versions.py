import hashlib
import json
import logging
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from mooshroom.config import ASSETS_DIR, LIBRARIES_DIR, VERSIONS_DIR
from mooshroom.java import get_java_executable, remove_java

logger = logging.getLogger(__name__)

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
RESOURCES_URL = "https://resources.download.minecraft.net"

OS_NAME_MAP = {"darwin": "osx", "linux": "linux", "win32": "windows"}


def _current_os() -> str:
    return OS_NAME_MAP.get(sys.platform, sys.platform)


def check_rules(rules: list[dict]) -> bool:
    if not rules:
        return True
    allowed = False
    for rule in rules:
        action = rule["action"] == "allow"
        os_rule = rule.get("os")
        if os_rule is None:
            allowed = action
        elif os_rule.get("name") == _current_os():
            allowed = action
    return allowed


def _sha1(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha1").hexdigest()


def _download(
    client: httpx.Client, url: str, dest: Path, expected_sha1: str | None = None
):
    if dest.exists() and expected_sha1 and _sha1(dest) == expected_sha1:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                f.write(chunk)
    if expected_sha1 and _sha1(dest) != expected_sha1:
        dest.unlink()
        raise RuntimeError(f"SHA1 mismatch for {dest.name}")


def fetch_manifest() -> dict:
    r = httpx.get(MANIFEST_URL, timeout=15)
    r.raise_for_status()
    return r.json()


def install_version(version_id: str):
    version_dir = VERSIONS_DIR / version_id
    meta_path = version_dir / f"{version_id}.json"

    if meta_path.exists():
        logger.info(f"{version_id} already installed.")
        return

    logger.info("Fetching version manifest...")
    manifest = fetch_manifest()
    version_entry = next(
        (v for v in manifest["versions"] if v["id"] == version_id), None
    )
    if not version_entry:
        raise RuntimeError(f"Version {version_id} not found.")

    version_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        logger.info("Downloading version metadata...")
        r = client.get(version_entry["url"])
        r.raise_for_status()
        meta = r.json()
        meta_path.write_text(json.dumps(meta, indent=2))

        client_info = meta["downloads"]["client"]
        jar_path = version_dir / f"{version_id}.jar"
        logger.info("Downloading client JAR...")
        _download(client, client_info["url"], jar_path, client_info["sha1"])

        lib_tasks = []
        for lib in meta["libraries"]:
            if not check_rules(lib.get("rules", [])):
                continue
            downloads = lib.get("downloads", {})
            artifact = downloads.get("artifact")
            if artifact:
                lib_tasks.append(
                    (
                        artifact["url"],
                        LIBRARIES_DIR / artifact["path"],
                        artifact["sha1"],
                    )
                )
            classifiers = downloads.get("classifiers", {})
            native_key = lib.get("natives", {}).get(_current_os())
            if native_key and native_key in classifiers:
                native = classifiers[native_key]
                lib_tasks.append(
                    (native["url"], LIBRARIES_DIR / native["path"], native["sha1"])
                )

        asset_index = meta["assetIndex"]
        index_path = ASSETS_DIR / "indexes" / f"{asset_index['id']}.json"
        logger.info(f"Downloading asset index ({asset_index['id']})...")
        _download(client, asset_index["url"], index_path, asset_index["sha1"])

        index_data = json.loads(index_path.read_text())
        asset_tasks = []
        for obj in index_data["objects"].values():
            h = obj["hash"]
            asset_tasks.append(
                (f"{RESOURCES_URL}/{h[:2]}/{h}", ASSETS_DIR / "objects" / h[:2] / h, h)
            )

        all_tasks = lib_tasks + asset_tasks
        logger.info(
            f"Downloading {len(lib_tasks)} libraries and {len(asset_tasks)} assets..."
        )
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda t: _download(client, *t), all_tasks))

    java_version = meta.get("javaVersion", {}).get("majorVersion")
    if java_version:
        logger.info(f"Ensuring Java {java_version} is available...")
        get_java_executable(java_version)

    logger.info(f"Installed {version_id}.")


def list_installed() -> list[str]:
    if not VERSIONS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in VERSIONS_DIR.iterdir()
        if d.is_dir() and (d / f"{d.name}.json").exists()
    )


def get_version_meta(version_id: str) -> dict:
    meta_path = VERSIONS_DIR / version_id / f"{version_id}.json"
    if not meta_path.exists():
        raise RuntimeError(f"Version {version_id} is not installed.")
    return json.loads(meta_path.read_text())


def _prune_dir(directory: Path, keep: set, key=None) -> int:
    if not directory.exists():
        return 0
    removed = 0
    for f in directory.rglob("*"):
        if f.is_file() and key(f) not in keep:
            f.unlink()
            removed += 1
    for d in sorted(directory.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass
    return removed


def delete_version(version_id: str):
    version_dir = VERSIONS_DIR / version_id
    if not version_dir.exists():
        raise RuntimeError(f"Version {version_id} is not installed.")

    meta = get_version_meta(version_id)
    java_version = meta.get("javaVersion", {}).get("majorVersion")
    shutil.rmtree(version_dir)
    logger.info(f"Removed {version_id}.")

    # Single pass over remaining versions for both cleanup and java check
    installed = list_installed()
    if not installed:
        if LIBRARIES_DIR.exists():
            shutil.rmtree(LIBRARIES_DIR)
        if ASSETS_DIR.exists():
            shutil.rmtree(ASSETS_DIR)
        if java_version:
            remove_java(java_version)
        return

    needed_libs = set()
    needed_assets = set()
    needed_indexes = set()
    needed_java = set()

    for vid in installed:
        m = get_version_meta(vid)
        jv = m.get("javaVersion", {}).get("majorVersion")
        if jv:
            needed_java.add(jv)
        for lib in m["libraries"]:
            if not check_rules(lib.get("rules", [])):
                continue
            downloads = lib.get("downloads", {})
            artifact = downloads.get("artifact")
            if artifact:
                needed_libs.add(Path(artifact["path"]))
            native_key = lib.get("natives", {}).get(_current_os())
            classifiers = downloads.get("classifiers", {})
            if native_key and native_key in classifiers:
                needed_libs.add(Path(classifiers[native_key]["path"]))
        asset_id = m["assetIndex"]["id"]
        needed_indexes.add(f"{asset_id}.json")
        index_path = ASSETS_DIR / "indexes" / f"{asset_id}.json"
        if index_path.exists():
            index_data = json.loads(index_path.read_text())
            for obj in index_data["objects"].values():
                needed_assets.add(obj["hash"])

    if java_version and java_version not in needed_java:
        remove_java(java_version)

    removed = _prune_dir(
        LIBRARIES_DIR, needed_libs, key=lambda f: f.relative_to(LIBRARIES_DIR)
    )
    removed += _prune_dir(ASSETS_DIR / "objects", needed_assets, key=lambda f: f.name)
    removed += _prune_dir(ASSETS_DIR / "indexes", needed_indexes, key=lambda f: f.name)

    if removed:
        logger.info(f"Cleaned up {removed} unused files.")
