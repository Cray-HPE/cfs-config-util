"""
Utility functions for activating or deactivating a version.

Copyright 2021 Hewlett Packard Enterprise Development LP
"""
import logging
import urllib.parse

from cfs_config_util.vcs import VCSRepo
from cfs_config_util.cfs import (
    CFSConfiguration,
    CFSConfigurationError,
)


LOGGER = logging.getLogger(__name__)


def get_local_path(clone_url):
    """Extract the path from a full URL.

    Args:
        clone_url (str): a clone url to get the repo path from.

    Returns:
        the path component of the URL (i.e. with the protocol and host
        information stripped)
    """
    return urllib.parse.urlparse(clone_url).path


def cfs_activate_version(product, version, cfs_layer_name, repo_url, playbook):
    """Activate a version of the product.

    Args:
        product (str): the name of the product to activate
        version (str): installed product version to activate
        cfs_layer_name (str): CFS configuration layer name to use for the product.
        repo_path (str): the full clone URL or the local path pointing to the
            git repository containing the configuration. (e.g.:
            "https://vcs.local/vcs/cray/sat-config-management.git" or just
            "/vcs/cray/sat-config-management.git")
        playbook (str): path to the playbook in the VCS configuration repo.

    Returns:
        a 2-tuple containing a list of names of configurations that were
        successfully updated, and a list of names of configurations that failed
        to update.
    """
    vcs_local_path = get_local_path(repo_url)
    cfg_repo = VCSRepo(vcs_local_path)
    commit_hash = cfg_repo.get_commit_hash_for_version(product, version)

    # TODO (CRAYSAT-1220): Figure out if we need to be able to query
    # configurations for other types of nodes.
    succeeded, failed = [], []
    for cfg in CFSConfiguration.get_configurations_for_components(role='Management', subrole='Master'):
        LOGGER.info('Updating CFS configuration "%s"', cfg.name)
        try:
            cfg.ensure_layer(cfs_layer_name, commit_hash, cfg_repo.clone_url, playbook)
            succeeded.append(cfg.name)
        except CFSConfigurationError as err:
            LOGGER.warning('Could not update CFS configuration "%s": %s', cfg.name, err)
            failed.append(cfg.name)
    return succeeded, failed


def cfs_deactivate_version(cfs_layer_name):
    """Deactivate a version of the product.

    Args:
        cfs_layer_name (str): the name of the layer used for the product.

    Returns:
        a 2-tuple containing a list of names of configurations that were
        successfully updated, and a list of names of configurations that failed
        to update.
    """
    # TODO (CRAYSAT-1220): Figure out if we need to be able to query
    # configurations for other types of nodes.
    succeeded, failed = [], []
    for cfg in CFSConfiguration.get_configurations_for_components(role='Management', subrole='Master'):
        LOGGER.info('Removing layer "%s" from CFS configuration "%s"', cfs_layer_name, cfg.name)
        try:
            cfg.remove_layer(cfs_layer_name)
            succeeded.append(cfg.name)
        except CFSConfigurationError as err:
            LOGGER.warning('Could not remove layer "%s" from CFS configuration "%s": %s',
                           cfs_layer_name, cfg.name, err)
            failed.append(cfg.name)
    return succeeded, failed
