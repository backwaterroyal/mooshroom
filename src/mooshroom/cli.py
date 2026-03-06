import click

from mooshroom.auth import device_code_login
from mooshroom.config import AUTH_FILE
from mooshroom.console import console
from mooshroom.launcher import launch
from mooshroom.profiles import (
    create_profile,
    delete_profile,
    edit_profile,
    game_dir_for,
    get_profile,
    list_profiles,
)
from mooshroom.versions import (
    delete_version,
    install_version,
    list_installed as list_versions,
)


@click.group()
def main():
    """A fast CLI Minecraft launcher and mod manager."""


# -- auth --


@main.group()
def auth():
    """Manage Microsoft account authentication."""


@auth.command()
def login():
    """Log in with a Microsoft account via device code flow."""
    tokens = device_code_login()
    console.print(f"Logged in as [bold]{tokens.username}[/]")


@auth.command()
def logout():
    """Remove stored auth tokens and log out."""
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        console.print("Logged out.")
    else:
        console.print("[info]Not logged in.[/]")


# -- version --


@main.group()
def version():
    """Manage Minecraft version installations."""


@version.command("list")
def version_list():
    """List locally installed Minecraft versions."""
    installed = list_versions()
    if not installed:
        console.print("[info]No versions installed.[/]")
        return
    for v in installed:
        console.print(f"  {v}")


@version.command()
@click.argument("version")
def install(version):
    """Download and install a Minecraft version."""
    install_version(version)


@version.command()
@click.argument("version")
def remove(version):
    """Remove an installed Minecraft version and its files."""
    delete_version(version)


# -- profile --


@main.group()
def profile():
    """Manage launch profiles for different configurations."""


@profile.command("list")
def profile_list():
    """List all saved profiles."""
    profiles = list_profiles()
    if not profiles:
        console.print("[info]No profiles created.[/]")
        return
    for name, p in profiles.items():
        console.print(f"  {name} [info]({p['version']})[/]")


@profile.command()
@click.argument("name")
@click.option("--version", "-v", required=True, help="Minecraft version to use.")
@click.option("--java-args", default=None, help="Custom JVM arguments.")
@click.option("--resolution", default=None, help="Window resolution as WIDTHxHEIGHT.")
def create(name, version, java_args, resolution):
    """Create a new launch profile."""
    width, height = None, None
    if resolution:
        try:
            w, h = resolution.split("x")
            width, height = int(w), int(h)
        except ValueError:
            raise click.UsageError("Resolution must be WIDTHxHEIGHT (e.g. 1920x1080).")
    create_profile(
        name, version, java_args=java_args,
        resolution_width=width, resolution_height=height,
    )
    console.print(f"Created profile [bold]{name}[/].")


@profile.command()
@click.argument("name")
def delete(name):
    """Delete a saved profile."""
    delete_profile(name)
    game_dir = game_dir_for(name)
    console.print(f"Deleted profile [bold]{name}[/].")
    if game_dir.exists():
        console.print(f"[info]Game data preserved at {game_dir}[/]")


@profile.command()
@click.argument("name")
@click.option("--version", "-v", default=None, help="Change Minecraft version.")
@click.option("--java-args", default=None, help="Change JVM arguments.")
@click.option("--resolution", default=None, help="Change resolution (WIDTHxHEIGHT).")
def edit(name, version, java_args, resolution):
    """Edit an existing profile's settings."""
    updates = {}
    if version is not None:
        updates["version"] = version
    if java_args is not None:
        updates["java_args"] = java_args
    if resolution is not None:
        try:
            w, h = resolution.split("x")
            updates["resolution_width"] = int(w)
            updates["resolution_height"] = int(h)
        except ValueError:
            raise click.UsageError("Resolution must be WIDTHxHEIGHT (e.g. 1920x1080).")
    if not updates:
        raise click.UsageError(
            "No changes specified. Use --version, --java-args, or --resolution."
        )
    edit_profile(name, **updates)
    console.print(f"Updated profile [bold]{name}[/].")


@profile.command("launch")
@click.argument("name")
@click.option("--offline", is_flag=True, help="Launch without authentication.")
def profile_launch(name, offline):
    """Launch Minecraft using the specified profile."""
    p = get_profile(name)
    version_id = p["version"]
    width = p.get("resolution_width")
    height = p.get("resolution_height")
    launch(
        version_id,
        game_dir=game_dir_for(name),
        java_args=p.get("java_args"),
        resolution_width=width if width is not None else 854,
        resolution_height=height if height is not None else 480,
        offline=offline,
    )
