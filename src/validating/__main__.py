"""
Contains the cli api of template.

NOTE: this module is private. All functions and objects are available in the main
`template` namespace - use that instead.

"""

import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
def run() -> None:
    """Read and display a config file."""
