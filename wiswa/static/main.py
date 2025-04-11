"""Main script."""
from __future__ import annotations

import logging

import click

__all__ = ('main',)


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-d', '--debug', help='Enable debug level logging.', is_flag=True)
def main(*, debug: bool = False) -> None:
    logging.basicConfig(format='%(levelname)s:%(module)s:%(lineno)d:%(funcName)s: %(message)s',
                        level=logging.DEBUG if debug else logging.WARNING)
    click.echo('Do something here.')
