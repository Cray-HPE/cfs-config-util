#
# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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

import argparse
import logging

from cfs_config_util.activation import cfs_activate_version


def configure_logging():
    """Configure logging for the cfs-config-util executable.

    This sets up the root logger with the default format, INFO log level, and
    stderr log handler.

    Returns:
        None.
    """
    CONSOLE_LOG_FORMAT = '%(levelname)s: %(message)s'
    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(CONSOLE_LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)


def main():
    configure_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument('version',
                        help='the version string corresponding to the Ansible configuration '
                        'to use when updating the CFS configuration.')
    args = parser.parse_args()

    # TODO: These should be configurable options. See CRAYSAT-1220.
    VCS_LOCAL_PATH = '/vcs/cray/sat-config-management.git'
    SAT_PRODUCT_NAME = 'sat'
    SAT_PLAYBOOK = 'sat-ncn.yml'

    cfs_activate_version(SAT_PRODUCT_NAME, args.version, VCS_LOCAL_PATH, SAT_PLAYBOOK)
