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
    """A fast CLI Minecraft launcher and mod manager."""
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# -- auth --


@main.group()
def auth():
    """Manage Microsoft account authentication."""


@auth.command()
def login():
    """Log in with a Microsoft account via device code flow."""
    tokens = device_code_login()
    click.echo(f"Logged in as {tokens.username}")


@auth.command()
def logout():
    """Remove stored auth tokens and log out."""
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        click.echo("Logged out.")
    else:
        click.echo("Not logged in.")


# -- version --


@main.group()
def version():
    """Manage Minecraft version installations."""


@version.command("list")
def version_list():
    """List locally installed Minecraft versions."""
    installed = list_versions()
    if not installed:
        click.echo("No versions installed.")
        return
    for v in installed:
        click.echo(f"  {v}")


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
    raise click.UsageError("Not yet implemented.")


@profile.command()
@click.argument("name")
def create(name):
    """Create a new launch profile with the given name."""
    raise click.UsageError("Not yet implemented.")


@profile.command()
@click.argument("name")
def delete(name):
    """Delete a saved profile."""
    raise click.UsageError("Not yet implemented.")


@profile.command()
@click.argument("name")
def edit(name):
    """Edit an existing profile's settings."""
    raise click.UsageError("Not yet implemented.")


@profile.command("launch")
@click.argument("name")
def profile_launch(name):
    """Launch Minecraft using the specified profile."""
    raise click.UsageError("Not yet implemented.")
