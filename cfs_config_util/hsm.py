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
Utility functions for interacting with the Hardware State Manager (HSM) API
"""
from copy import deepcopy

from cfs_config_util.errors import CFSConfigUtilError
from csm_api_client.service.gateway import APIError


def get_node_ids(hsm_client, component_ids=None, hsm_query=None):
    """Get the node component IDs to which a CFS configuration should be applied.

    Args:
        component_ids (list, Optional): the list of explicit ids (xnames) given, if any
        hsm_query (dict, Optional): HSM query parameters to find components
        hsm_client (csm_api_client.service.hsm.HSMClient): the HSM API client

    Returns:
        list: the list of component ids (xnames)

    Raises:
        CFSConfigUtilError: if there is an error querying the HSM API
    """
    if component_ids is None:
        component_ids = []
    else:
        # Make a copy to avoid modifying the passed in argument
        component_ids = list(component_ids)

    if hsm_query:
        query_params = deepcopy(hsm_query)
        query_params['type'] = 'Node'
        try:
            component_ids.extend(hsm_client.get_component_xnames(query_params))
        except APIError as err:
            raise CFSConfigUtilError(
                f'Unable to query HSM for components matching parameters {query_params}: {err}'
            ) from err

    return component_ids
