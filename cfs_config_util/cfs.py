"""
Basic client library for CFS.

Copyright 2021 Hewlett Packard Enterprise Development LP
"""

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import json
import logging

from cfs_config_util.apiclient import APIError, CFSClient, HSMClient
from cfs_config_util.session import AdminSession


LOGGER = logging.getLogger(__name__)


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

    @contextmanager
    def updatable_layers(self):
        """Get a list of layers which can be modified and updated after use.

        This function returns a context manager which, when bound with a with/as
        clause, is a list of layers as stored in CFS. This list can be manipulated
        as desired, and the updated list will then be sent to CFS after the
        context manager exits.

        Returns:
            context manager which yields a list of layers.

        Raises:
            CFSConfigurationError: if CFS cannot be updated.
        """
        new_layers = deepcopy(self.config.get('layers'))

        yield new_layers

        new_config = {'layers': new_layers}
        try:
            self._cfs_client.put('v2', 'configurations', self.name, json=new_config)
        except APIError as err:
            raise CFSConfigurationError(f'Could not update CFS configuration "{self.name}": {err}')

        self.config.update(new_config)
        LOGGER.info('Successfully updated layers in configuration "%s"', self.name)

    def remove_layer(self, layer_name):
        """Removes a layer from the configuration.

        Args:
            layer_name (str): name of the layer to remove

        Returns:
            None.

        Raises:
            CFSConfigurationError: if CFS cannot be updated or if there are
                duplicate layers with the given name.
        """
        self.check_duplicate_layer_names(layer_name)

        LOGGER.info('Removing layer "%s" from configuration "%s"',
                    layer_name, self.name)
        with self.updatable_layers() as new_layers:
            removal_index = None
            for index, layer in enumerate(new_layers):
                if layer.get('name') == layer_name:
                    removal_index = index
                    break

            if removal_index is not None:
                del new_layers[removal_index]
            else:
                LOGGER.warning('Layer "%s" not found in configuration "%s"; continuing.',
                               layer_name, self.name)

    def ensure_layer(self, layer_name, commit_hash, clone_url, playbook):
        """Ensures a layer exists with the given parameters.

        Args:
            layer_name (str): the name of the layer
            commit_hash (str): the commit hash of the configuration to use in
                VCS
            clone_url (str): the URL in VCS containing the configuration
            playbook (str): the path to the playbook in the VCS repo

        Returns: None.

        Raises:
            CFSConfigurationError: if CFS cannot be updated or if there are
                duplicate layers with the given name.
        """
        self.check_duplicate_layer_names(layer_name)

        new_layer_base = {
            'commit': commit_hash,
            'cloneUrl': clone_url,
            'playbook': playbook,
        }

        with self.updatable_layers() as new_layers:
            for layer in new_layers:
                if layer['name'] == layer_name:
                    LOGGER.info('Found existing layer with name "%s" in configuration "%s"; updating.',
                                layer_name, self.name)
                    for new_layer_key, new_value in new_layer_base.items():
                        if layer[new_layer_key] != new_value:
                            LOGGER.info('Key "%s" in layer "%s" updated from "%s" to "%s"',
                                        new_layer_key, layer_name,
                                        layer[new_layer_key], new_value)
                    layer.update(new_layer_base)
                    break
            else:
                new_layer = dict(name=layer_name, **new_layer_base)
                LOGGER.info('Layer with name "%s" was not found in configuration "%s". '
                            'Appending layer with the following contents: %s',
                            layer_name, self.name, new_layer)
                new_layers.append(new_layer)

    def check_duplicate_layer_names(self, layer_name):
        """Exits the program if the layer name is not unique.

        Args:
            layer_name (str): the name of the layer to check

        Returns:
            None

        Raises:
            CFSConfigurationError: if there are multiple layers with name layer_name.
        """
        # TODO: Exiting here may not be the best general solution. See
        # CRAYSAT-1221.
        counts_by_name = Counter([layer.get('name') for layer in self.layers])
        layers_with_name = counts_by_name.get(layer_name, 0)
        if layers_with_name > 1:
            raise CFSConfigurationError(f'{layers_with_name} found with name "{layer_name}"'
                                        ' in configuration "{self.name}"')
