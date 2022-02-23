"""
Utility functions for activating or deactivating a version.

Copyright 2021-2022 Hewlett Packard Enterprise Development LP
"""
import json
import logging
import urllib.parse

from cfs_config_util.vcs import VCSRepo
from cfs_config_util.cfs import (
    CFSConfiguration,
    CFSConfigurationError,
    LayerState
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


def ensure_product_layer(product, version, repo_url, playbook, state):
    """Ensure a CFS configuration layer is present or absent for a product.

    Args:
        product (str): the name of the product to activate
        version (str): installed product version to activate
        repo_url (str): the full clone URL or the local path pointing to the
            git repository containing the configuration. (e.g.:
            "https://vcs.local/vcs/cray/sat-config-management.git" or just
            "/vcs/cray/sat-config-management.git")
        playbook (str): path to the playbook in the VCS configuration repo.
        state (LayerState): whether to ensure the layer is present or absent

    Returns:
        A tuple of the following items:
            succeeded (list of str): names of configurations successfully updated
            failed (list of str): names of configurations that failed to be updated
    """
    vcs_local_path = get_local_path(repo_url)
    cfg_repo = VCSRepo(vcs_local_path)
    commit_hash = cfg_repo.get_commit_hash_for_version(product, version)
    layer_name = f'{product}-{version}'

    # TODO (CRAYSAT-1220): Figure out if we need to be able to query
    # configurations for other types of nodes.
    hsm_params = {'role': 'Management', 'subrole': 'Master'}
    succeeded, failed = [], []
    for cfg in CFSConfiguration.get_configurations_for_components(**hsm_params):
        LOGGER.info('Updating CFS configuration "%s"', cfg.name)
        try:
            cfg.ensure_layer(layer_name, commit_hash, cfg_repo.clone_url, playbook, state=state)
            succeeded.append(cfg.name)
        except CFSConfigurationError as err:
            LOGGER.warning('Could not update CFS configuration "%s": %s', cfg.name, err)
            failed.append(cfg.name)

    if not succeeded and not failed:
        descriptor = ' and '.join([f'{param} {value}'
                                   for param, value in hsm_params.items()])
        LOGGER.warning(f'No CFS configurations found that apply to components with '
                       f'{descriptor}.')
        new_layer = {
            'name': layer_name,
            'commit': commit_hash,
            'cloneUrl': cfg_repo.clone_url,
            'playbook': playbook,
        }
        LOGGER.info(f'The following {product} layer should be used in the CFS configuration that '
                    f'will be applied to NCNs with {descriptor}.\n{json.dumps(new_layer, indent=4)}')

    return succeeded, failed


def cfs_activate_version(product, version, repo_url, playbook):
    """Activate a product version by adding/updating its CFS layer for NCNs.

    See `ensure_product_layer` for details on the args and return value.
    """
    return ensure_product_layer(product, version, repo_url, playbook, LayerState.PRESENT)


def cfs_deactivate_version(product, version, repo_url, playbook):
    """Deactivate a product version by removing its CFS layer for NCNs.

    See `ensure_product_layer` for details on the args and return value.
    """
    return ensure_product_layer(product, version, repo_url, playbook, LayerState.ABSENT)
