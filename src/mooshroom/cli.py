import logging

import click

from mooshroom.auth import device_code_login
from mooshroom.config import AUTH_FILE
from mooshroom.launcher import launch
from mooshroom.versions import (
    delete_version,
    install_version,
    list_installed as list_versions,
)


@click.group()
def main():
    """Minimal Minecraft launcher."""
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@main.command()
@click.argument("version")
def install(version):
    """Install a Minecraft version."""
    install_version(version)


@main.command()
def versions():
    """List installed versions."""
    installed = list_versions()
    if not installed:
        click.echo("No versions installed.")
        return
    for v in installed:
        click.echo(f"  {v}")


@main.command()
@click.argument("version")
def remove(version):
    """Remove an installed version."""
    delete_version(version)


@main.command("launch")
@click.argument("version")
def launch_cmd(version):
    """Launch a Minecraft version."""
    launch(version)


@main.command()
def login():
    """Log in with Microsoft account."""
    tokens = device_code_login()
    click.echo(f"Logged in as {tokens.username}")


@main.command()
def logout():
    """Remove stored auth tokens."""
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        click.echo("Logged out.")
    else:
        click.echo("Not logged in.")
