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
Basic client library for CFS.
"""
from enum import Enum
import json
import logging
from urllib.parse import urlparse

from cfs_config_util.apiclient import APIError, CFSClient, HSMClient
from cfs_config_util.session import AdminSession

LOGGER = logging.getLogger(__name__)


class LayerState(Enum):
    """Desired state of a layer in a CFSConfiguration."""
    PRESENT = 'present'
    ABSENT = 'absent'


class CFSConfigurationError(Exception):
    """Represents an error that occurred while modifying CFS."""


class CFSConfiguration:
    """Represents a single configuration in CFS.

    Attributes:
        name (str): the name of the configuration
    """
    def __init__(self, name):
        self._cfs_client = CFSClient(AdminSession.get_session())
        self.name = name
        try:
            self.config = self._cfs_client.get('v2', 'configurations', name).json()
        except APIError as err:
            raise CFSConfigurationError(f'Could not retrieve configuration "{name}" from CFS: {err}')
        except json.JSONDecodeError as err:
            raise CFSConfigurationError(f'Invalid JSON response received from CFS: {err}')

    @classmethod
    def get_configurations_for_components(cls, **kwargs):
        """Configurations for components matching the given params.

        Parameters passed into this function should be valid HSM component
        attributes.

        Args:
            kwargs: parameters which are passed to HSM to filter queried components.

        Yields:
            CFSConfiguration: the relevant configs marked as desired for the
                given components.

        Raises:
            CFSConfigurationError: if there is an error accessing HSM or CFS.
        """
        session = AdminSession.get_session()
        hsm_client = HSMClient(session)
        cfs_client = CFSClient(session)

        try:
            target_xnames = hsm_client.get_component_xnames(params=kwargs or None)
        except APIError as err:
            raise CFSConfigurationError(f'Could not retrieve xnames from HSM matching params {kwargs}: {err}')

        LOGGER.info('Querying CFS configurations for the following NCNs: %s',
                    ', '.join(target_xnames))

        desired_config_names = set()
        for xname in target_xnames:
            try:
                desired_config_name = cfs_client.get('v2', 'components', xname) \
                                                .json() \
                                                .get('desiredConfig')
                if desired_config_name:
                    LOGGER.info('Found configuration "%s" for component %s',
                                desired_config_name, xname)
                    desired_config_names.add(desired_config_name)
            except APIError as err:
                LOGGER.warning('Could not retrieve CFS configuration for component %s: %s',
                               xname, err)
            except json.JSONDecodeError as err:
                LOGGER.warning('CFS returned invalid JSON for component %s: %s',
                               xname, err)

        for config_name in desired_config_names:
            if config_name is not None:
                yield cls(config_name)

    @property
    def layers(self):
        """[dict]: The layers of this configuration"""
        return self.config.get('layers')

    @staticmethod
    def layer_matches(layer, repo_path, playbook):
        """Determine whether the given layer matches the given clone URL and playbook.

        Args:
            layer (dict): the layer data
            repo_path (str): the repo path to check against
            playbook (str): the playbook to check against

        Returns:
            True if the layer matches, False otherwise.
        """
        layer_repo_path = urlparse(layer.get('cloneUrl')).path
        return layer_repo_path == repo_path and layer.get('playbook') == playbook

    def update_layers(self, layers):
        """Update the layers of the configuration.

        Args:
            layers (list of dict): the layers to update the configuration with

        Returns: None

        Raises:
            CFSConfigurationError: if the update of the CFS configuration fails
        """
        req_payload = {'layers': layers}
        try:
            response_json = self._cfs_client.put('v2', 'configurations', self.name, json=req_payload).json()
        except APIError as err:
            raise CFSConfigurationError(f'Failed to update CFS configuration "{self.name}": {err}')
        except ValueError as err:
            raise CFSConfigurationError(f'Failed to decode JSON response from updating '
                                        f'CFS configuration "{self.name}": {err}')

        self.config.update(response_json)
        LOGGER.info('Successfully updated layers in configuration "%s"', self.name)

    def ensure_layer(self, layer_name, commit_hash, clone_url, playbook, state=LayerState.PRESENT):
        """Ensure a layer exists or does not exist with the given parameters.

        Args:
            layer_name (str): the name of the layer
            commit_hash (str): the commit hash of the configuration to use in
                VCS
            clone_url (str): the URL in VCS containing the configuration
            playbook (str): the path to the playbook in the VCS repo
            state (LayerState): whether to ensure the layer is present or absent

        Returns: None.

        Raises:
            CFSConfigurationError: if the CFS configuration cannot be updated
        """
        action = ('Removing', 'Updating')[state is LayerState.PRESENT]
        repo_path = urlparse(clone_url).path
        layer_description = f'layer with repo path {repo_path} and playbook {playbook}'

        new_layer = {
            'name': layer_name,
            'commit': commit_hash,
            'cloneUrl': clone_url,
            'playbook': playbook,
        }

        new_layers = []
        found_match = False
        made_changes = False
        for layer in self.layers:
            if self.layer_matches(layer, repo_path, playbook):
                found_match = True
                LOGGER.info('%s existing %s in configuration "%s".',
                            action, layer_description, self.name)
                if state is LayerState.ABSENT:
                    # Skip adding this layer to new_layers
                    made_changes = True
                    continue

                # Layer should be present. Check if it differs at all.
                for new_layer_key, new_value in new_layer.items():
                    if layer.get(new_layer_key) != new_value:
                        made_changes = True
                        LOGGER.info('Key "%s" in %s updated from %s to %s',
                                    new_layer_key, layer_description,
                                    layer.get(new_layer_key), new_value)
                new_layers.append(new_layer)
            else:
                # This layer doesn't match, so leave it untouched
                new_layers.append(layer)

        if not found_match:
            LOGGER.info('No %s found in configuration "%s". ', layer_description, self.name)
            if state is LayerState.PRESENT:
                LOGGER.info('Adding a %s to the configuration "%s"',
                            layer_description, self.name)
                made_changes = True
                new_layers.append(new_layer)

        if made_changes:
            self.update_layers(new_layers)
        else:
            LOGGER.info('No changes to configuration "%s" were necessary.', self.name)
