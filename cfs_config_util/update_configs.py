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
Implementation of the update-configs action of cfs-config-utility
"""
from copy import deepcopy
from datetime import datetime
import json
import logging

from csm_api_client.service.cfs import (
    CFSClientBase,
    CFSConfigurationError,
    CFSConfigurationLayer
)
from csm_api_client.service.gateway import APIError
from csm_api_client.service.hsm import HSMClient
from csm_api_client.session import AdminSession

from cfs_config_util.environment import (
    API_CERT_VERIFY,
    API_GW_HOST,
)
from cfs_config_util.errors import CFSConfigUtilError
from cfs_config_util.hsm import get_node_ids
from cfs_config_util.parser import (
    base_given,
    apply_options_provided,
    assign_requested
)
from cfs_config_util.update_components import update_cfs_components
from cfs_config_util.wait import wait_for_component_configuration

LOGGER = logging.getLogger(__name__)


def get_cfs_configurations(args, cfs_client, hsm_client):
    """Get the CFSConfigurations from CFS or from a file.

    Args:
        args (argparse.Namespace): the parsed command-line args
        cfs_client (csm_api_client.service.cfs.CFSClientBase): the CFS API client
        hsm_client (cfs_config_util.apiclient.HSMClient): the HSM API client

    Returns:
        list of csm_api_client.service.cfs.CFSConfigurationBase: the CFS configurations
            from CFS or loaded from a file. If a name of a CFS config or a file
            name is given, the list will have only one element.

    Raises:
        CFSConfigurationError: if unable get the CFS configuration from the CFS
            API or unable to load it from a file
    """
    if args.base_config is not None:
        # Get the CFS configuration from the CFS API
        try:
            return [cfs_client.get_configuration(args.base_config)]
        except APIError as err:
            raise CFSConfigurationError(f'Could not retrieve configuration '
                                        f'"{args.base_config}" from CFS: {err}') from err

    elif args.base_query is not None:
        # Only HSM components of type Node have corresponding CFS components
        hsm_query_params = deepcopy(args.base_query)
        hsm_query_params['type'] = 'Node'
        try:
            configs = cfs_client.get_configurations_for_components(hsm_client, **hsm_query_params)
            if not configs:
                raise CFSConfigurationError(
                    f'No configurations were found for components matching the '
                    f'query "{hsm_query_params}".'
                )
            return configs
        except APIError as err:
            raise CFSConfigurationError(
                f'Could not retrieve CFS configurations for HSM components '
                f'matching the query "{hsm_query_params}": {err}'
            )

    else:
        # args.base_file must have been specified, so load from a file
        try:
            with open(args.base_file, 'r') as f:
                file_data = json.load(f)
        except OSError as err:
            raise CFSConfigurationError(f'Failed to open file {args.base_file}: {err}')
        except json.decoder.JSONDecodeError as err:
            raise CFSConfigurationError(f'Failed to parse JSON in file {args.base_file}: {err}')

        return [cfs_client.configuration_cls(cfs_client, file_data)]


def construct_layers(args):
    """Construct CFSConfigurationLayer(s) which should be added or removed from a CFSConfigurationBase.

    Args:
        args (argparse.Namespace): the parsed command-line args

    Returns:
        List[CFSConfigurationLayer]: the layers that should be added or removed

    Raises:
        CFSConfigurationError: if unable to construct the requested layer
    """
    # These kwargs are common between both layers defined by clone URL and layers
    # defined by product.
    layers = []
    playbooks = args.playbooks

    # If the --playbook option is not supplied, then only create one layer with
    # the default playbook. Passing `None` as the playbook argument to the
    # layer creation methods achieves this.
    if playbooks is None:
        playbooks = [None]

    for playbook in playbooks:
        common_args = {
            'name': args.layer_name,
            'playbook': playbook,
            'commit': args.git_commit,
            'branch': args.git_branch
        }
        if args.product:
            if ':' in args.product:
                product_name, product_version = args.product.split(':', maxsplit=1)
            else:
                product_name = args.product
                product_version = None
            layers.append(
                CFSConfigurationLayer.from_product_catalog(
                    product_name, API_GW_HOST, product_version=product_version, **common_args)
            )
        else:
            layers.append(
                CFSConfigurationLayer.from_clone_url(args.clone_url, **common_args)
            )
    return layers


def save_cfs_configuration(args, cfs_config):
    """Save the CFSConfigurationBase to a file or to CFS per the command-line args.

    Args:
        args (argparse.Namespace): the parsed command-line args
        cfs_config (csm_api_client.service.cfs.CFSConfigurationBase): the modified
            CFS configuration to save

    Returns:
        CFSConfigurationBase or None: if a new CFS configuration was saved to CFS,
            return the new CFSConfigurationBase object.

    Raises:
        CFSConfigurationError: if unable to save the CFS configuration to CFS
            or to a file.
    """
    backup_suffix = None
    if args.create_backups:
        backup_suffix = f'-backup-{datetime.now().strftime("%Y%m%dT%H%M%S")}'

    if args.save:
        if args.base_config or args.base_query:
            # Overwrite the CFS configuration in CFS
            return cfs_config.save_to_cfs(backup_suffix=backup_suffix)
        else:
            # args.base_file; overwrite the file in place
            cfs_config.save_to_file(args.base_file, backup_suffix=backup_suffix)

    elif args.save_suffix:
        if args.base_config or args.base_query:
            return cfs_config.save_to_cfs(f'{cfs_config.name}{args.save_suffix}',
                                          backup_suffix=backup_suffix)
        else:
            cfs_config.save_to_file(f'{args.base_file}{args.save_suffix}',
                                    backup_suffix=backup_suffix)

    elif args.save_to_cfs:
        return cfs_config.save_to_cfs(args.save_to_cfs, overwrite=base_given(args),
                                      backup_suffix=backup_suffix)

    elif args.save_to_file:
        cfs_config.save_to_file(args.save_to_file, overwrite=base_given(args),
                                backup_suffix=backup_suffix)


def get_affected_components(cfs_client, cfs_configs):
    """Get CFS components which have one of the configs as their desiredConfig.

    Args:
        cfs_client (csm_api_client.service.cfs.CFSClientBase): the CFS API client
        cfs_configs (csm_api_client.service.cfs.CFSConfigurationBase): the CFS
            configurations to check

    Returns:
        set: the IDs of the CFS components which use any of the given
            `cfs_configurations`

    Raises:
         CFSConfigUtilError: if there is a failure to get affected components
    """
    affected_components = set()
    for cfs_config in cfs_configs:
        try:
            affected_components.update(cfs_client.get_component_ids_using_config(cfs_config.name))
        except APIError as err:
            raise CFSConfigUtilError(f'Failed to get affected components: {err}') from err

    return affected_components


def update_configurations(args, cfs_client, hsm_client):
    """Update the CFS configurations as requested by command-line args

    Args:
        args (argparse.Namespace): the parsed command-line arguments
        cfs_client (csm_api_client.service.cfs.CFSClientBase): the CFS API client
        hsm_client (csm_api_client.service.hsm.HSMClient): the HSM API client

    Returns:
        A tuple consisting of the CFSConfigurationBase objects which have been
        updated and those which did not need to be updated.
    """
    try:
        if base_given(args):
            base_configs = get_cfs_configurations(args, cfs_client, hsm_client)
        else:
            LOGGER.info('No base configuration given. Starting from empty configuration. '
                        'Existing configurations will not be overwritten.')
            base_configs = [cfs_client.configuration_cls.empty(cfs_client)]

        layers = construct_layers(args)

    except CFSConfigurationError as err:
        LOGGER.error(str(err))
        raise SystemExit(1)

    # List of CFS configs which were updated in CFS, updated in a file, not modified, or failed
    updated_cfs_configs, updated_file_configs, unmodified_configs, failed = [], [], [], []
    for base_config in base_configs:
        for layer in layers:
            if args.resolve_branches:
                layer.resolve_branch_to_commit_hash()
            base_config.ensure_layer(layer, args.state)

        if not base_config.changed:
            unmodified_configs.append(base_config)
            continue

        try:
            updated_config = save_cfs_configuration(args, base_config)
            if updated_config is None:
                updated_file_configs.append(base_config)
            else:
                updated_cfs_configs.append(updated_config)
        except CFSConfigurationError as err:
            LOGGER.error(str(err))
            failed.append(base_config)

    if unmodified_configs:
        LOGGER.info(f'Skipped saving {len(unmodified_configs)} unchanged CFS configuration(s).')
    if updated_cfs_configs:
        LOGGER.info(f'Successfully saved {len(updated_cfs_configs)} changed CFS '
                    f'configuration(s) to CFS.')
    if updated_file_configs:
        LOGGER.info(f'Successfully saved {len(updated_cfs_configs)} changed CFS '
                    f'configuration(s) to file(s).')
    if failed:
        LOGGER.error(f'Failed to save {len(failed)} CFS configuration(s).')
        raise SystemExit(1)

    return updated_cfs_configs, unmodified_configs


def assign_configuration(args, cfs_client, hsm_client, cfs_config_name):
    """Assign a configuration to the components according to CLI args.

    Args:
        args (argparse.Namespace): the parsed command-line arguments
        cfs_client (csm_api_client.service.cfs.CFSClientBase): the CFS API client
        hsm_client (csm_api_client.service.hsm.HSMClient): the HSM API client
        cfs_config_name (str): CFS configuration name to assign to components

    Returns:
        list of str: component IDs to which configuration was assigned
    """
    try:
        assign_components = get_node_ids(hsm_client, component_ids=args.assign_to_xnames,
                                         hsm_query=args.assign_to_query)
    except CFSConfigUtilError as err:
        LOGGER.error(f'Failed to get components to which configuration '
                     f'should be assigned: {err}')
        raise SystemExit(1)

    try:
        update_cfs_components(
            cfs_client, assign_components, desired_config=cfs_config_name,
            clear_state=args.clear_state, clear_error=args.clear_error, enabled=args.enabled
        )
    except CFSConfigUtilError as err:
        LOGGER.error(f'Failed to update CFS components: {err}')
        raise SystemExit(1)

    return assign_components


def do_update_configs(args):
    """Update or create a CFS configuration.

    Args:
        args (argparse.Namespace): the parsed command-line arguments
    """
    session = AdminSession(API_GW_HOST, API_CERT_VERIFY)
    hsm_client = HSMClient(session)
    cfs_client = CFSClientBase.get_cfs_client(session, args.cfs_version)

    modified_configs, unmodified_configs = update_configurations(args, cfs_client, hsm_client)

    # These components are using a CFS configuration updated above
    affected_components = get_affected_components(cfs_client, modified_configs)
    # Update these components' other fields as requested by "Apply Options"
    if apply_options_provided(args):
        update_cfs_components(cfs_client, affected_components, clear_state=args.clear_state,
                              clear_error=args.clear_error, enabled=args.enabled)

    # Assign the configuration to any components as requested
    assigned_components = []
    if assign_requested(args):
        all_configs = modified_configs + unmodified_configs

        # Neither of these cases should happen given how arguments are checked,
        # specifically that --base-query and assign are not allowed together
        if len(all_configs) != 1:
            LOGGER.error(f'Expected a single configuration to apply to CFS '
                         f'components but found {len(all_configs)}')
            raise SystemExit(1)

        assigned_components = assign_configuration(args, cfs_client, hsm_client, all_configs[0].name)

    affected_components.update(assigned_components)

    if args.wait and affected_components:
        wait_for_component_configuration(cfs_client, affected_components)
