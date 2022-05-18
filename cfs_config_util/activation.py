"""
Utility functions for activating or deactivating a version.

Copyright 2021-2022 Hewlett Packard Enterprise Development LP
"""
import logging

from cfs_config_util.apiclient import APIError, HSMClient
from cfs_config_util.cfs import (
    CFSClient,
    CFSConfigurationLayer,
    CFSConfigurationError,
    LayerState
)
from cfs_config_util.session import AdminSession


LOGGER = logging.getLogger(__name__)


def ensure_product_layer(product, version, playbook, state,
                         hsm_query_params, git_commit=None, git_branch=None):
    """Ensure the product layer is present/absent in CFS configuration(s).

    This queries HSM for components matching the hsm_query_params and then
    queries CFS to find the CFS configurations that apply to those components.
    Those CFS configurations are then updated in place.

    Args:
        product (str): the name of the product
        version (str): the version of the product
        playbook (str): path to the playbook in the VCS configuration repo.
        state (LayerState): the expected state for the layer
        hsm_query_params (dict): query parameters to pass to HSM to find the
            components which should have their configurations updated
        git_commit (str or None): the git commit hash to use in the layer
        git_branch (str or None): the git branch to use in the layer. If neither
            commit hash nor branch are specified, the commit hash from the product
            catalog is used. Provide only one of git_branch or git_commit.

    Returns:
        tuple: lists of names of CFSConfigurations which were successfully
            updated and which failed to be updated.

    Raises:
        CFSConfigurationError: if there is a failure when querying HSM for
            component IDs or CFS for configurations that apply to those
            components.
    """
    # This can raise CFSConfigurationError
    product_layer = CFSConfigurationLayer.from_product_catalog(
        product, version, playbook=playbook,
        commit=git_commit, branch=git_branch
    )

    # Protect against callers accidentally updating CFS configs that apply to all components
    if not hsm_query_params:
        raise CFSConfigurationError(f'HSM query parameters must be specified.')

    session = AdminSession.get_session()
    hsm_client = HSMClient(session)
    cfs_client = CFSClient(session)

    try:
        cfs_configs = cfs_client.get_configurations_for_components(hsm_client, **hsm_query_params)
    except APIError as err:
        raise CFSConfigurationError(f'Failed to query CFS or HSM for component configurations: {err}')

    succeeded, failed = [], []
    for cfs_config in cfs_configs:
        LOGGER.info(f'Updating CFS configuration {cfs_config.name}.')
        cfs_config.ensure_layer(product_layer, state)
        try:
            cfs_config.save_to_cfs()
            succeeded.append(cfs_config.name)
        except CFSConfigurationError as err:
            LOGGER.warning(f'Could not update CFS configuration {cfs_config.name}: {err}')
            failed.append(cfs_config.name)

    return succeeded, failed


def cfs_activate_version(product, version, playbook, hsm_query_params,
                         git_commit=None, git_branch=None):
    """Activate a product version by adding/updating its CFS layer to relevant CFS configs.

    See `ensure_product_layer` for details on the args and return value.
    """
    return ensure_product_layer(product, version, playbook, LayerState.PRESENT,
                                hsm_query_params, git_commit, git_branch)


def cfs_deactivate_version(product, version, playbook, hsm_query_params,
                           git_commit=None, git_branch=None):
    """Deactivate a product version by removing its CFS layer from relevant CFS configs.

    See `ensure_product_layer` for details on the args and return value.
    """
    return ensure_product_layer(product, version, playbook, LayerState.ABSENT,
                                hsm_query_params, git_commit, git_branch)
