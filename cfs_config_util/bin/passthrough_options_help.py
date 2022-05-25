"""
Entry point used by product installers to obtain help on the passthrough options.

Copyright 2022 Hewlett Packard Enterprise Development LP
"""

from cfs_config_util.parser import create_passthrough_parser


def main():
    """Output help for the passthrough options.

    Passthrough options are the options which are exposed to the system admin
    through a script in the product release distribution.

    Returns:
        None
    """
    parser = create_passthrough_parser()
    parser.print_help()
