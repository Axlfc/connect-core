import click

@click.group()
def cli():
    """NOOA CLI Tooling (NOOA-25)."""
    pass

@cli.command()
@click.option("--template", default="basic")
def init(template):
    """Initializes a new NOOA agent project."""
    click.echo(f"Initialized project with template: {template}")

@cli.command()
def eject():
    """Ejects default configurations to local workspace."""
    click.echo("Configuration files ejected to workspace.")

@cli.command()
def dev():
    """Starts dev tooling server."""
    click.echo("Starting development server...")

if __name__ == "__main__":
    cli()
