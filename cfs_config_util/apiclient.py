# MIT License
#
# (C) Copyright 2019-2022 Hewlett Packard Enterprise Development LP
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
Client for querying the API gateway.
"""

import logging
from urllib.parse import urlunparse
import warnings

from kubernetes.client import CoreV1Api
from kubernetes.config import load_kube_config
from kubernetes.config.config_exception import ConfigException
import requests
from yaml import YAMLLoadWarning

from cfs_config_util.environment import API_CERT_VERIFY, API_GW_HOST, API_TIMEOUT

LOGGER = logging.getLogger(__name__)


def load_kube_api():
    """Get a Kubernetes CoreV1Api object.

    This helper function loads the kube config and then instantiates
    an API object.

    Returns:
        CoreV1Api: the API object from the kubernetes library.

    Raises:
        kubernetes.config.config_exception.ConfigException: if failed to load
            kubernetes configuration.
    """
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=YAMLLoadWarning)
            load_kube_config()
    # Earlier versions: FileNotFoundError; later versions: ConfigException
    except (FileNotFoundError, ConfigException) as err:
        raise ConfigException(
            'Failed to load kubernetes config to get pod status: '
            '{}'.format(err)
        )

    return CoreV1Api()


class APIError(Exception):
    """An exception occurred when making a request to the API."""


class ReadTimeout(Exception):
    """An timeout occurred when making a request to the API."""


class APIGatewayClient:
    """A client to the API Gateway."""

    # This can be set in subclasses to make a client for a specific API
    base_resource_path = ''

    def __init__(self, session=None, host=None, cert_verify=None, timeout=None):
        """Initialize the APIGatewayClient.

        Args:
            session: The Session instance to use when making REST calls,
                or None to make connections without a session.
            host (str): The API gateway host.
            cert_verify (bool): Whether to verify the gateway's certificate.
            timeout (int): number of seconds to wait for a response before timing
                out requests made to services behind the API gateway.
        """

        # Inherit parameters from session if not passed as arguments
        # If there is no session, get the values from the environment

        if host is None:
            if session is None:
                host = API_GW_HOST
            else:
                host = session.host

        if cert_verify is None:
            if session is None:
                cert_verify = API_CERT_VERIFY
            else:
                cert_verify = session.cert_verify

        self.session = session
        self.host = host
        self.cert_verify = cert_verify
        self.timeout = API_TIMEOUT if timeout is None else timeout

    def set_timeout(self, timeout):
        self.timeout = timeout

    def _make_req(self, *args, req_type='GET', req_param=None, json=None):
        """Perform HTTP request with type `req_type` to resource given in `args`.
        Args:
            *args: Variable length list of path components used to construct
                the path to the resource.
            req_type (str): Type of reqest (GET, STREAM, POST, PUT, or DELETE).
            req_param: Parameter(s) depending on request type.
            json (dict): The data dict to encode as JSON and pass as the body of
                a POST request.

        Returns:
            The requests.models.Response object if the request was successful.

        Raises:
            ReadTimeout: if the req_type is STREAM and there is a ReadTimeout.
            APIError: if the status code of the response is >= 400 or request
                raises a RequestException of any kind.
        """
        url = urlunparse(('https', self.host, 'apis/{}{}'.format(
            self.base_resource_path, '/'.join(args)), '', '', ''))

        LOGGER.debug("Issuing %s request to URL '%s'", req_type, url)

        if self.session is None:
            requester = requests
        else:
            requester = self.session.session

        try:
            if req_type == 'GET':
                r = requester.get(url, params=req_param, verify=self.cert_verify, timeout=self.timeout)
            elif req_type == 'STREAM':
                r = requester.get(url, params=req_param, stream=True,
                                  verify=self.cert_verify, timeout=self.timeout)
            elif req_type == 'POST':
                r = requester.post(url, data=req_param, verify=self.cert_verify,
                                   json=json, timeout=self.timeout)
            elif req_type == 'PUT':
                r = requester.put(url, data=req_param, verify=self.cert_verify,
                                  json=json, timeout=self.timeout)
            elif req_type == 'PATCH':
                r = requester.patch(url, data=req_param, verify=self.cert_verify, timeout=self.timeout)
            elif req_type == 'DELETE':
                r = requester.delete(url, verify=self.cert_verify, timeout=self.timeout)
            else:
                # Internal error not expected to occur.
                raise ValueError("Request type '{}' is invalid.".format(req_type))
        except requests.exceptions.ReadTimeout as err:
            if req_type == 'STREAM':
                raise ReadTimeout("{} request to URL '{}' timeout: {}".format(req_type, url, err))
            else:
                raise APIError("{} request to URL '{}' failed: {}".format(req_type, url, err))
        except requests.exceptions.RequestException as err:
            raise APIError("{} request to URL '{}' failed: {}".format(req_type, url, err))

        LOGGER.debug("Received response to %s request to URL '%s' "
                     "with status code: '%s': %s", req_type, r.url, r.status_code, r.reason)

        if not r.ok:
            api_err_msg = (f"{req_type} request to URL '{url}' failed with status "
                           f"code {r.status_code}: {r.reason}")
            # Attempt to get more information from response
            try:
                problem = r.json()
            except ValueError:
                raise APIError(api_err_msg)

            if 'title' in problem:
                api_err_msg += f'. {problem["title"]}'
            if 'detail' in problem:
                api_err_msg += f' Detail: {problem["detail"]}'

            raise APIError(api_err_msg)

        return r

    def get(self, *args, params=None):
        """Issue an HTTP GET request to resource given in `args`.

        Args:
            *args: Variable length list of path components used to construct
                the path to the resource to GET.
            params (dict): Parameters dictionary to pass through to request.get.

        Returns:
            The requests.models.Response object if the request was successful.

        Raises:
            APIError: if the status code of the response is >= 400 or requests.get
                raises a RequestException of any kind.
        """

        r = self._make_req(*args, req_type='GET', req_param=params)

        return r

    def stream(self, *args, params=None):
        """Issue an HTTP GET stream request to resource given in `args`.

        Args:
            *args: Variable length list of path components used to construct
                the path to the resource to GET.
            params (dict): Parameters dictionary to pass through to request.get.

        Returns:
            The requests.models.Response object if the request was successful.

        Raises:
            ReadTimeout: if there is a ReadTimeout.
            APIError: if the status code of the response is >= 400 or requests.get
                raises a RequestException of any kind.
        """

        r = self._make_req(*args, req_type='STREAM', req_param=params)

        return r

    def post(self, *args, payload=None, json=None):
        """Issue an HTTP POST request to resource given in `args`.

        Args:
            *args: Variable length list of path components used to construct
                the path to POST target.
            payload: The encoded data to send as the POST body.
            json: The data dict to encode as JSON and send as the POST body.

        Returns:
            The requests.models.Response object if the request was successful.

        Raises:
            APIError: if the status code of the response is >= 400 or requests.post
                raises a RequestException of any kind.
        """

        r = self._make_req(*args, req_type='POST', req_param=payload, json=json)

        return r

    def put(self, *args, payload=None, json=None):
        """Issue an HTTP PUT request to resource given in `args`.

        Args:
            *args: Variable length list of path components used to construct
                the path to PUT target.
            payload: JSON data to put.

        Returns:
            The requests.models.Response object if the request was successful.

        Raises:
            APIError: if the status code of the response is >= 400 or requests.put
                raises a RequestException of any kind.
        """

        r = self._make_req(*args, req_type='PUT', req_param=payload, json=json)

        return r

    def patch(self, *args, payload):
        """Issue an HTTP PATCH request to resource given in `args`.

        Args:
            *args: Variable length list of path components used to construct
                the path to PATCH target.
            payload: JSON data to put.

        Returns:
            The requests.models.Response object if the request was successful.

        Raises:
            APIError: if the status code of the response is >= 400 or requests.put
                raises a RequestException of any kind.
        """

        r = self._make_req(*args, req_type='PATCH', req_param=payload)

        return r

    def delete(self, *args):
        """Issue an HTTP DELETE resource given in `args`.

        Args:
            *args: Variable length list of path components used to construct
                the path to DELETE target.

        Returns:
            The requests.models.Response object if the request was successful.

        Raises:
            APIError: if the status code of the response is >= 400 or requests.delete
                raises a RequestException of any kind.
        """

        r = self._make_req(*args, req_type='DELETE')

        return r


class HSMClient(APIGatewayClient):
    base_resource_path = 'smd/hsm/v2/'

    def get_bmcs_by_type(self, bmc_type=None, check_keys=True):
        """Get a list of BMCs, optionally of a single type.

        Args:
            bmc_type (string): Any HSM BMC type: NodeBMC, RouterBMC or ChassisBMC.
            check_keys (bool): Whether or not to filter data based on missing keys.

        Returns:
            A list of dictionaries where each dictionary describes a BMC.

        Raises:
            APIError: if the API query failed or returned an invalid response.
        """
        try:
            response = self.get(
                'Inventory', 'RedfishEndpoints', params={'type': bmc_type} if bmc_type else {}
            )
        except APIError as err:
            raise APIError(f'Failed to get BMCs from HSM API: {err}')

        try:
            redfish_endpoints = response.json()['RedfishEndpoints']
        except ValueError as err:
            raise APIError(f'API response could not be parsed as JSON: {err}')
        except KeyError as err:
            raise APIError(f'API response missing expected key: {err}')

        # Check that the returned data has expected keys, and exclude data without it.
        invalid_redfish_endpoint_xnames = []
        if check_keys:
            invalid_redfish_endpoint_xnames = [
                endpoint.get('ID') for endpoint in redfish_endpoints
                if any(required_key not in endpoint for required_key in ['ID', 'Enabled', 'DiscoveryInfo'])
                or 'LastDiscoveryStatus' not in endpoint['DiscoveryInfo']
            ]
        if invalid_redfish_endpoint_xnames:
            LOGGER.warning(
                'The following xnames were excluded due to incomplete information from HSM: %s',
                ', '.join(invalid_redfish_endpoint_xnames)
            )

        return [
            endpoint for endpoint in redfish_endpoints
            if endpoint.get('ID') not in invalid_redfish_endpoint_xnames
        ]

    def get_component_xnames(self, params=None, omit_empty=True):
        """Get the xnames of components matching the given criteria.

        If any args are omitted, the results are not limited by that criteria.

        Args:
            params (dict): the parameters to pass in the GET request to the
                '/State/Components' URL in HSM. E.g.:
                    {
                        'type': 'Node',
                        'role': 'Compute',
                        'class': 'Mountain'
                    }
            omit_empty (bool): if True, omit the components with "State": "Empty"

        Returns:
            list of str: the xnames matching the given filters

        Raises:
            APIError: if there is a failure querying the HSM API or getting
                the required information from the response.
        """
        if params:
            params_string = f' with {", ".join(f"{key}={value}" for key, value in params.items())}'
        else:
            params_string = ''

        err_prefix = f'Failed to get components{params_string}.'

        try:
            components = self.get('State', 'Components', params=params).json()['Components']
        except APIError as err:
            raise APIError(f'{err_prefix}: {err}')
        except ValueError as err:
            raise APIError(f'{err_prefix} due to bad JSON in response: {err}')
        except KeyError as err:
            raise APIError(f'{err_prefix} due to missing {err} key in response.')

        try:
            if omit_empty:
                return [component['ID'] for component in components
                        if component['State'] != 'Empty']
            else:
                return [component['ID'] for component in components]
        except KeyError as err:
            raise APIError(f'{err_prefix} due to missing {err} key in list of components.')

    def get_node_components(self):
        """Get the components of Type=Node from HSM.

        Returns:
            list of dictionaries of Node components.

        Raises:
            APIError: if there is a failure querying the HSM API or getting
                the required information from the response.
        """

        err_prefix = 'Failed to get Node components'
        try:
            components = self.get('State', 'Components', params={'type': 'Node'}).json()['Components']
        except APIError as err:
            raise APIError(f'{err_prefix}: {err}')
        except ValueError as err:
            raise APIError(f'{err_prefix} due to bad JSON in response: {err}')
        except KeyError as err:
            raise APIError(f'{err_prefix} due to missing {err} key in response.')

        return components

    def get_all_components(self):
        """Get all components from HSM.

        Returns:
            components ([dict]): A list of dictionaries from HSM.

        Raises:
            APIError: if there is a failure querying the HSM API or getting
                the required information from the response.
        """

        err_prefix = 'Failed to get HSM components'
        try:
            components = self.get('State', 'Components').json()['Components']
        except APIError as err:
            raise APIError(f'{err_prefix}: {err}')
        except ValueError as err:
            raise APIError(f'{err_prefix} due to bad JSON in response: {err}')
        except KeyError as err:
            raise APIError(f'{err_prefix} due to missing {err} key in response.')

        return components

    def get_component_history_by_id(self, cid=None, by_fru=False):
        """Get component history from HSM, optionally for a single ID or FRUID.

        Args:
            cid (str or None): A component ID which is either an xname or FRUID or None.
            by_fru (bool): if True, query HSM history using HardwareByFRU.

        Returns:
            components ([dict]): A list of dictionaries from HSM with component history or None.

        Raises:
            APIError: if there is a failure querying the HSM API or getting
                the required information from the response.
        """
        err_prefix = 'Failed to get HSM component history'
        params = {}
        if by_fru:
            inventory_type = 'HardwareByFRU'
            if cid:
                params = {'fruid': cid}
        else:
            inventory_type = 'Hardware'
            if cid:
                params = {'id': cid}

        try:
            components = self.get('Inventory', inventory_type, 'History', params=params).json()['Components']
        except APIError as err:
            raise APIError(f'{err_prefix}: {err}')
        except ValueError as err:
            raise APIError(f'{err_prefix} due to bad JSON in response: {err}')
        except KeyError as err:
            raise APIError(f'{err_prefix} due to missing {err} key in response.')

        return components

    def get_component_history(self, cids=None, by_fru=False):
        """Get component history from HSM.

        Args:
            cids (set(str)): A set of component IDs which are either an xname or FRUID or None.
            by_fru (bool): if True, query HSM history using HardwareByFRU.

        Returns:
            components ([dict]): A list of dictionaries from HSM with component history.

        Raises:
            APIError: if there is a failure querying the HSM API or getting
                the required information from the response.
        """

        if not cids:
            components = self.get_component_history_by_id(None, by_fru)
        else:
            components = []
            for cid in cids:
                # An exception is raised if HSM API returns a 400 when
                # an xname has an invalid format.
                # If the cid is a FRUID or a correctly formatted xname
                # that does not exist in the hardware inventory,
                # then None is returned because History is an empty list.
                # In either case (exception or None is returned),
                # keep going and try to get history for other cids.
                try:
                    component_history = self.get_component_history_by_id(cid, by_fru)
                    if component_history:
                        components.extend(component_history)
                except APIError as err:
                    LOGGER.debug(f'HSM API error for {cid}: {err}')

        return components
