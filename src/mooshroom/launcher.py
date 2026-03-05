import subprocess
import sys
from string import Template

import click

from mooshroom.auth import refresh_or_login
from mooshroom.config import ASSETS_DIR, DATA_DIR, LIBRARIES_DIR, VERSIONS_DIR
from mooshroom.console import console
from mooshroom.java import get_java_executable
from mooshroom.versions import check_rules, get_version_meta

_PATH_SEP = ";" if sys.platform == "win32" else ":"


def _process_args(args_list: list, variables: dict[str, str]) -> list[str]:
    result = []
    for arg in args_list:
        if isinstance(arg, str):
            result.append(Template(arg).safe_substitute(variables))
        elif isinstance(arg, dict):
            if not check_rules(arg.get("rules", [])):
                continue
            value = arg.get("value", [])
            if isinstance(value, str):
                result.append(Template(value).safe_substitute(variables))
            elif isinstance(value, list):
                result.extend(Template(v).safe_substitute(variables) for v in value)
    return result


def launch(version_id: str):
    meta = get_version_meta(version_id)

    java_version = meta.get("javaVersion", {}).get("majorVersion", 21)
    java_path = get_java_executable(java_version)

    tokens = refresh_or_login()

    lib_paths = []
    for lib in meta["libraries"]:
        if not check_rules(lib.get("rules", [])):
            continue
        artifact = lib.get("downloads", {}).get("artifact")
        if artifact:
            lib_paths.append(str(LIBRARIES_DIR / artifact["path"]))
    lib_paths.append(str(VERSIONS_DIR / version_id / f"{version_id}.jar"))
    classpath = _PATH_SEP.join(lib_paths)

    natives_dir = VERSIONS_DIR / version_id / "natives"
    natives_dir.mkdir(exist_ok=True)

    game_dir = DATA_DIR / "game"
    game_dir.mkdir(parents=True, exist_ok=True)

    variables = {
        "natives_directory": str(natives_dir),
        "launcher_name": "mooshroom",
        "launcher_version": "0.1.0",
        "classpath": classpath,
        "classpath_separator": _PATH_SEP,
        "library_directory": str(LIBRARIES_DIR),
        "auth_player_name": tokens.username,
        "version_name": version_id,
        "game_directory": str(game_dir),
        "assets_root": str(ASSETS_DIR),
        "assets_index_name": meta["assetIndex"]["id"],
        "auth_uuid": tokens.uuid,
        "auth_access_token": tokens.mc_access_token,
        "clientid": "",
        "auth_xuid": "",
        "user_type": "msa",
        "version_type": meta.get("type", "release"),
        "resolution_width": "854",
        "resolution_height": "480",
        "quickPlayPath": "",
        "quickPlaySingleplayer": "",
        "quickPlayMultiplayer": "",
        "quickPlayRealms": "",
    }

    jvm_args = []
    if "arguments" in meta:
        jvm_args = _process_args(meta["arguments"].get("jvm", []), variables)
        game_args = _process_args(meta["arguments"].get("game", []), variables)
    elif "minecraftArguments" in meta:
        jvm_args = [f"-Djava.library.path={natives_dir}", "-cp", classpath]
        game_args = [
            Template(a).safe_substitute(variables)
            for a in meta["minecraftArguments"].split()
        ]
    else:
        raise click.ClickException("Unknown argument format in version metadata")

    main_class = meta["mainClass"]
    cmd = [str(java_path)] + jvm_args + [main_class] + game_args

    console.print(f"Launching {version_id}...")
    process = subprocess.Popen(cmd, cwd=str(game_dir))
    console.print(f"[info]Game running (PID {process.pid}).[/]")
    process.wait()
