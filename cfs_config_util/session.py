#
# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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
OAuth2 authentication support.
"""

import base64
import json
import logging
import os.path
import os

from oauthlib.oauth2 import LegacyApplicationClient
import requests
from requests_oauthlib import OAuth2Session

from cfs_config_util.apiclient import load_kube_api
from cfs_config_util.cached_property import cached_property
from cfs_config_util.environment import API_GW_HOST, API_CERT_VERIFY

LOGGER = logging.getLogger(__name__)


class AdminSession:
    """Manage API sessions, authentication, and token storage/retrieval.

    This Session class differs from the SAT authentication mechanism as it
    retrieves the admin credentials from a Kubernetes secret instead of using
    user account credentials. This Session is a singleton class.
    """

    _session = None
    TOKEN_URI = '/keycloak/realms/{}/protocol/openid-connect/token'
    tenant = 'shasta'
    client_id = 'shasta'

    def __init__(self):
        """Initialize a Session. Wraps an OAuth2Session.

        Parameter management. Initialization of the OAuth2Session passes to
        self.get_session().
        """
        self.host = API_GW_HOST
        self.cert_verify = API_CERT_VERIFY

        client = LegacyApplicationClient(client_id=self.client_id, token=self.token)
        client.parse_request_body_response(json.dumps(self.token))

        self.session = OAuth2Session(client=client, token=self.token)

    @cached_property
    def token(self):
        """dict: Deserialized authentication token.
        """
        k8s = load_kube_api()
        admin_client_auth = k8s.read_namespaced_secret('admin-client-auth', 'default')
        auth_req_payload = {
            'grant_type': 'client_credentials',
            'client_id': 'admin-client',
            'client_secret': base64.b64decode(admin_client_auth.data['client-secret']).decode()
        }
        resp = requests.post(f'https://{self.host}{self.TOKEN_URI.format(self.tenant)}',
                             verify=self.cert_verify, data=auth_req_payload)
        return resp.json()

    @classmethod
    def get_session(cls):
        """Get a reused session object.

        Returns: a session object that will be cached.
        """
        if cls._session is None:
            cls._session = AdminSession()
        return cls._session
