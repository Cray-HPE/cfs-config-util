"""
Main entrypoint to CFS update utility

Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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
