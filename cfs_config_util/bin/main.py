#
# MIT License
#
# (C) Copyright 2021-2024 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""
Main entrypoint to CFS update utility
"""

import logging

from cfs_config_util.parser import (
    CANONICAL_UPDATE_CONFIGS_ACTION,
    CANONICAL_UPDATE_COMPONENTS_ACTION,
    check_args,
    create_parser
)
from cfs_config_util.update_components import do_update_components
from cfs_config_util.update_configs import do_update_configs

LOGGER = logging.getLogger(__name__)


def configure_logging(verbose=False):
    """Configure logging for the cfs-config-util executable.

    This sets up the root logger with the default format, INFO log level, and
    stderr log handler.

    Returns:
        None.
    """
    level = logging.DEBUG if verbose else logging.INFO
    console_log_format = '%(levelname)s: %(message)s'
    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(console_log_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(level)


def log_args_and_exit(args):
    from enum import Enum
    import json

    # Make the args.state value JSON serializable
    class CustomEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, Enum):
                return o.value
            return super().default(o)

    LOGGER.debug(json.dumps(vars(args), cls=CustomEncoder, indent=4))
    raise SystemExit(0)


def main():
    """Modify a CFS configuration and save it as specified by the command-line args.

    Returns:
        None

    Raises:
        SystemExit: if there is a failure to get the base config, modify it, or save it
    """
    parser = create_parser()
    args = parser.parse_args()
    configure_logging(verbose=args.verbose)
    log_args_and_exit(args)

    try:
        check_args(args)
    except ValueError as err:
        LOGGER.error(str(err))
        raise SystemExit(1)

    LOGGER.debug(f'Received action "{args.action}" which corresponds to '
                 f'canonical action "{args.canonical_action}".')

    functions_by_action = {
        CANONICAL_UPDATE_CONFIGS_ACTION: do_update_configs,
        CANONICAL_UPDATE_COMPONENTS_ACTION: do_update_components
    }
    do_action = functions_by_action.get(args.canonical_action)
    do_action(args)
