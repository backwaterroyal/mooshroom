import logging
import platform
import shutil
from pathlib import Path

import httpx

from mooshroom.config import JAVA_DIR

logger = logging.getLogger(__name__)

ADOPTIUM_API = "https://api.adoptium.net/v3"


def _get_os_arch() -> tuple[str, str]:
    system_map = {"Darwin": "mac", "Linux": "linux", "Windows": "windows"}
    arch_map = {
        "x86_64": "x64",
        "AMD64": "x64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }
    return system_map[platform.system()], arch_map[platform.machine()]


def install_java(major_version: int):
    dest = JAVA_DIR / str(major_version)
    if dest.exists():
        logger.info(f"Java {major_version} already installed.")
        return

    os_name, arch = _get_os_arch()
    logger.info(f"Fetching Java {major_version} for {os_name}/{arch}...")

    with httpx.Client(timeout=600, follow_redirects=True) as client:
        r = client.get(
            f"{ADOPTIUM_API}/assets/latest/{major_version}/hotspot",
            params={"os": os_name, "architecture": arch, "image_type": "jdk"},
        )
        r.raise_for_status()
        assets = r.json()

        if not assets:
            raise RuntimeError(
                f"No Adoptium JDK found for Java {major_version} ({os_name}/{arch})"
            )

        pkg = assets[0]["binary"]["package"]
        filename = pkg["name"]

        logger.info(f"Downloading {filename}...")
        dest.mkdir(parents=True, exist_ok=True)
        archive_path = dest / filename

        with client.stream("GET", pkg["link"]) as resp:
            resp.raise_for_status()
            with open(archive_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                    f.write(chunk)

    logger.info("Extracting...")
    shutil.unpack_archive(archive_path, dest)

    archive_path.unlink()
    logger.info(f"Java {major_version} installed.")


def list_installed() -> list[int]:
    if not JAVA_DIR.exists():
        return []
    return sorted(
        int(d.name) for d in JAVA_DIR.iterdir() if d.is_dir() and d.name.isdigit()
    )


def remove_java(major_version: int):
    dest = JAVA_DIR / str(major_version)
    if not dest.exists():
        logger.info(f"Java {major_version} is not installed.")
        return
    shutil.rmtree(dest)
    logger.info(f"Java {major_version} removed.")


def get_java_executable(major_version: int) -> Path:
    dest = JAVA_DIR / str(major_version)
    if not dest.exists():
        install_java(major_version)
    candidates = list(dest.glob("*/bin/java"))
    if not candidates:
        candidates = list(dest.glob("*/Contents/Home/bin/java"))
    if not candidates:
        raise RuntimeError(f"Could not find java binary in {dest}")
    return candidates[0]
