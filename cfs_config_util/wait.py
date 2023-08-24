#
# MIT License
#
# (C) Copyright 2023 Hewlett Packard Enterprise Development LP
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
Functions for waiting on CFS components to become configured.
"""
from collections import defaultdict
import logging
import time

from csm_api_client.service.gateway import APIError


LOGGER = logging.getLogger(__name__)


def get_components_by_status(cfs_client, component_ids):
    """Get a dict mapping component state to a list of components in that state.

    Args:
        cfs_client (csm_api_client.service.cfs.CFSClient): the CFS API client
        component_ids (Iterable): the component IDs to query

    Returns:
        tuple: a tuple (components_by_status, disabled_components, error_components)
            components_by_status: a dictionary mapping from CFS component state
                to a set of components in that state
            disabled_components: a set of components which are disabled
            error_components: a set of components which could not be queried in
                CFS
    """
    disabled_components = set()
    error_components = set()
    components_by_status = defaultdict(set)
    for component_id in component_ids:
        try:
            component_data = cfs_client.get('components', component_id).json()
        except (APIError, ValueError) as err:
            LOGGER.error(f'Failed to get CFS component "{component_id}": {err}')
            error_components.add(component_id)
        else:
            if component_data['enabled']:
                components_by_status[component_data['configurationStatus']].add(component_id)
            else:
                disabled_components.add(component_id)

    return components_by_status, disabled_components, error_components


def log_component_status_summary(components_by_status):

    summary = ", ".join(f'{status}: {len(ids)}'
                        for status, ids in components_by_status.items()
                        if ids)
    if summary:
        LOGGER.info(f'Summary of number of components in each status: {summary}')


def wait_for_component_configuration(cfs_client, wait_component_ids, check_interval=30):
    """Wait for CFS components to finish their configuration.

    This means waiting until all components have exited the "pending" state
    and reached either "configured" or "failed" states.

    Args:
        cfs_client (csm_api_client.service.cfs.CFSClient): the CFS API client
        wait_component_ids (Iterable): the component IDs to wait on
        check_interval (int): the number of seconds to wait between checks on
            component state

    Returns:
        None
    """
    LOGGER.info(f'Waiting for {len(wait_component_ids)} component(s) to finish '
                f'configuration')

    components_by_status, disabled_components, error_components = \
        get_components_by_status(cfs_client, wait_component_ids)

    if disabled_components:
        LOGGER.info(f'Ignoring {len(disabled_components)} disabled component(s): '
                    f'{", ".join(disabled_components)}')
    if error_components:
        LOGGER.warning(f'Ignoring {len(error_components)} component(s) which could not '
                       f'be queried: {", ".join(error_components)}')

    log_component_status_summary(components_by_status)

    pending_components = components_by_status['pending']
    LOGGER.info(f'Waiting for {len(pending_components)} pending component(s)')

    while pending_components:
        LOGGER.info(f'Sleeping for {check_interval} seconds before checking '
                    f'status of {len(pending_components)} pending component(s).')
        time.sleep(check_interval)

        new_components_by_status, new_disabled_components, new_error_components = \
            get_components_by_status(cfs_client, pending_components)

        for status, component_ids in new_components_by_status.items():
            if status != 'pending':
                LOGGER.info(f'{len(component_ids)} pending components transitioned '
                            f'to status {status}: {", ".join(component_ids)}')
                components_by_status[status].update(component_ids)
                pending_components -= component_ids

        if new_error_components:
            error_components.extend(new_error_components)
            pending_components -= new_error_components
        if new_disabled_components:
            LOGGER.info(f'{len(new_disabled_components)} component(s) have been '
                        f'disabled: {", ".join(disabled_components)}')
            pending_components -= new_disabled_components

    if error_components:
        LOGGER.warning(f'Failed to get status of {len(error_components)} component(s).')

    LOGGER.info(f'Finished waiting for {len(wait_component_ids)} '
                f'component(s) to finish configuration.')
    log_component_status_summary(components_by_status)
