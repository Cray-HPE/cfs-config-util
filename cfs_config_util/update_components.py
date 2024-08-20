#
# MIT License
#
# (C) Copyright 2023-2024 Hewlett Packard Enterprise Development LP
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
Implementation of the update-components action of cfs-config-utility
"""
import logging

from cfs_config_util.environment import (
    API_CERT_VERIFY,
    API_GW_HOST,
)
from cfs_config_util.errors import CFSConfigUtilError
from cfs_config_util.hsm import get_node_ids
from cfs_config_util.wait import wait_for_component_configuration

from csm_api_client.service.cfs import CFSClientBase
from csm_api_client.service.gateway import APIError
from csm_api_client.service.hsm import HSMClient
from csm_api_client.session import AdminSession

LOGGER = logging.getLogger(__name__)


def update_cfs_components(cfs_client, component_ids, desired_config=None, clear_state=None,
                          clear_error=None, enabled=None):
    """Assign the CFSConfiguration to the given CFS components.

    Args:
        cfs_client (csm_api_client.service.cfs.CFSClientBase): the CFS API client
        component_ids (Iterable): the list of component ids (xnames) to update
        desired_config (str, Optional): the name of the desired config to set
            on the components, if any
        clear_state (bool, Optional): if True, clear state of the component
        clear_error (bool, Optional): if True, clear errorCount of the component
        enabled (bool, Optional): if specified, set the enabled of the component

    Returns:
        None

    Raises:
        CFSConfigUtilError: if unable to assign the CFS configuration to any
            of the requested components.
    """
    failed_components = []
    for component_id in component_ids:
        try:
            cfs_client.update_component(component_id, desired_config=desired_config,
                                        clear_state=clear_state, clear_error=clear_error,
                                        enabled=enabled)
        except APIError as err:
            LOGGER.error(f'Failed to update CFS component {component_id}: {err}')
            failed_components.append(component_id)

    if failed_components:
        raise CFSConfigUtilError(f'Failed to update {len(failed_components)} '
                                 f'CFS components: {", ".join(failed_components)}')

    LOGGER.info(f'Updated {len(component_ids)} CFS components.')


def do_update_components(args):
    """Update CFS components.

    Args:
        args (argparse.Namespace): the parsed command-line arguments
    """
    session = AdminSession(API_GW_HOST, API_CERT_VERIFY)
    hsm_client = HSMClient(session)
    cfs_client = CFSClientBase.get_cfs_client(session, args.cfs_version)

    component_ids = get_node_ids(hsm_client, component_ids=args.xnames,
                                 hsm_query=args.query)
    LOGGER.info(f'Found {len(component_ids)} CFS components to update.')

    try:
        update_cfs_components(
            cfs_client, component_ids, desired_config=args.desired_config,
            clear_state=args.clear_state, clear_error=args.clear_error,
            enabled=args.enabled
        )
    except CFSConfigUtilError as err:
        LOGGER.error(str(err))
        raise SystemExit(1)

    if args.wait:
        wait_for_component_configuration(cfs_client, component_ids)
