"""Main script."""
from __future__ import annotations

import click

from .utils import setup_logging

__all__ = ('main',)


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-d', '--debug', help='Enable debug level logging.', is_flag=True)
def main(*, debug: bool = False, force_color: bool = False, no_color: bool = False) -> None:
    """Entry point."""
    setup_logging(debug=debug)
    click.echo('Do something here.')
