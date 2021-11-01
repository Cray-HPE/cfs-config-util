"""
Main entrypoint to CFS update utility

(C) Copyright 2021 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

import argparse
import logging
from urllib.parse import urlunparse

from cfs_config_util.cfs import (
    CFSConfiguration,
    get_cfs_configurations,
    get_remote_refs,
)


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


LOGGER = logging.getLogger(__name__)


def main():
    configure_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument('version',
                        help='the version string corresponding to the Ansible configuration '
                        'to use when updating the CFS configuration. This version string '
                        'may be prefixed with "sat-".')
    args = parser.parse_args()

    # TODO: These should be configurable options. See CRAYSAT-1220.
    VCS_USERNAME = 'crayvcs'
    VCS_LOCAL_HOST = 'api-gw-service-nmn.local'  # TODO: Update per CRAYSAT-898
    VCS_LOCAL_PATH = '/vcs/cray/sat-config-management.git'
    BASE_CLONE_URL = urlunparse(('https', VCS_LOCAL_HOST, VCS_LOCAL_PATH, '', '', ''))
    SAT_CFS_LAYER_NAME = 'sat-ncn'
    SAT_PLAYBOOK = 'sat-ncn.yml'

    LOGGER.info('Retrieving available Ansible configurations from VCS')
    remote_refs = get_remote_refs(VCS_USERNAME, VCS_LOCAL_HOST, VCS_LOCAL_PATH)

    target_version = args.version.split('sat-').pop()
    target_ref = f'refs/heads/cray/sat/{target_version}'
    if target_ref not in remote_refs:
        LOGGER.error('Installed target version not in local VCS (could not find ref "%s")',
                     target_ref)
        raise SystemExit(1)
    else:
        LOGGER.info('Found matching Ansible configuration at remote ref "%s" in VCS',
                    target_ref)

    for cfg in get_cfs_configurations():
        LOGGER.info('Updating CFS configuration "%s"', cfg)
        CFSConfiguration(cfg).update_layer(SAT_CFS_LAYER_NAME, remote_refs[target_ref], BASE_CLONE_URL, SAT_PLAYBOOK)
