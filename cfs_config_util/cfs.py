"""
Basic client library for CFS.

Copyright 2021-2022 Hewlett Packard Enterprise Development LP
"""
import os.path
from datetime import datetime
import json
from enum import Enum
import logging
from urllib.parse import urlparse, urlunparse

from cray_product_catalog.query import ProductCatalog, ProductCatalogError

from cfs_config_util.apiclient import APIError, APIGatewayClient
from cfs_config_util.environment import API_GW_HOST
from cfs_config_util.vcs import VCSError, VCSRepo

LOGGER = logging.getLogger(__name__)


class CFSClient(APIGatewayClient):
    base_resource_path = 'cfs/'

    def get_configuration(self, name):
        """Get a CFS configuration by name."""
        try:
            config_data = self.get('v2', 'configurations', name).json()
        except APIError as err:
            raise APIError(f'Could not retrieve configuration "{name}" from CFS: {err}')
        except json.JSONDecodeError as err:
            raise APIError(f'Invalid JSON response received from CFS when getting '
                           f'configuration "{name}" from CFS: {err}')
        return CFSConfiguration(self, config_data)

    def get_configurations_for_components(self, hsm_client, **kwargs):
        """Configurations for components matching the given params.

        Parameters passed into this function should be valid HSM component
        attributes.

        Args:
            hsm_client (HSMClient): the HSM client to use to query HSM for
                component IDs
            kwargs: parameters which are passed to HSM to filter queried components.

        Returns:
            list of CFSConfiguration: the relevant configs marked as desired for the
                given components

        Raises:
            APIError: if there is an error accessing HSM or CFS APIs
        """
        target_xnames = hsm_client.get_component_xnames(params=kwargs or None)

        LOGGER.info('Querying CFS configurations for the following NCNs: %s',
                    ', '.join(target_xnames))

        desired_config_names = set()
        for xname in target_xnames:
            try:
                desired_config_name = self.get('v2', 'components', xname).json().get('desiredConfig')
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

        return [self.get_configuration(config_name) for config_name in desired_config_names]


class LayerState(Enum):
    """Desired state of a layer in a CFSConfiguration."""
    PRESENT = 'present'
    ABSENT = 'absent'

    def __str__(self):
        """Use just the value as the string method.

        This allows its use as the value of the `choices` parameter in the
        add_argument method of argparse.ArgumentParser while still providing
        clear help text to the user.
        """
        return self.value


class CFSConfigurationError(Exception):
    """Represents an error that occurred while modifying CFS."""


class CFSConfigurationLayer:
    """A layer in a CFS configuration."""

    # A mapping from the properties in CFS response data to attributes of this class
    CFS_PROPS_TO_ATTRS = {
        'cloneUrl': 'clone_url',
        'commit': 'commit',
        'branch': 'branch',
        'name': 'name',
        'playbook': 'playbook'
    }
    ATTRS_TO_CFS_PROPS = {val: key for key, val in CFS_PROPS_TO_ATTRS.items()}

    def __init__(self, clone_url, name=None, playbook=None, commit=None, branch=None):
        """Create a new CFSConfiguration.

        Args:
            clone_url (str): the git repository clone URL
            name (str, optional): the name of the CFS configuration layer. The
                name is optional.
            playbook (str, optional): the name of the Ansible playbook. If
                omitted, the CFS-internal default is used.
            commit (str, optional): the commit hash to use. Either `commit` or
                `branch` is required.
            branch (str, optional): the git branch to use. Either `commit` or
                `branch` is required.

        Raises:
            ValueError: if neither `commit` nor `branch` is specified.
        """
        self.clone_url = clone_url
        self.name = name
        self.playbook = playbook
        if not (commit or branch):
            raise ValueError('Either commit or branch is required to create '
                             'a CFSConfigurationLayer.')
        self.commit = commit
        self.branch = branch

    @property
    def repo_path(self):
        """str: the path portion of the clone URL, e.g. /vcs/cray/sat-config-management.git"""
        return urlparse(self.clone_url).path

    def matches(self, other_layer):
        """Determine whether this layer matches the given layer.

        Args:
            other_layer (CFSConfigurationLayer): the layer data

        Returns:
            True if the layer matches, False otherwise.
        """
        if not(isinstance(other_layer, CFSConfigurationLayer)):
            return False

        return self.repo_path == other_layer.repo_path and self.playbook == other_layer.playbook

    def get_updated_values(self, new_layer):
        """Get the values which have been updated by the new version of this layer.

        Args:
            new_layer (CFSConfigurationLayer): the new layer to compare this one to

        Returns:
            dict: A dict mapping from the names of updated properties to a tuple
                which contains the old and new values.
        """
        updated_values = {}
        for cfs_prop, attr in self.CFS_PROPS_TO_ATTRS.items():
            old_value = getattr(self, attr)
            new_value = getattr(new_layer, attr)
            if old_value != new_value:
                updated_values[cfs_prop] = (old_value, new_value)
        return updated_values

    def resolve_branch_to_commit_hash(self):
        """Resolve a branch to a commit hash and specify only the commit hash.

        Returns:
            None. Modifies `self.branch` and `self.commit`.

        Raises:
            CFSConfigurationError: if there is a failure to resolve the branch
                to a commit hash.
        """
        if not self.branch:
            # No branch to translate to commit
            return

        vcs_repo = VCSRepo(self.clone_url)
        if self.commit:
            LOGGER.info("%s already specifies a commit hash (%s) and branch (%s); "
                        "overwriting commit hash with latest from branch",
                        self, self.commit, self.branch)
        try:
            self.commit = vcs_repo.get_commit_hash_for_branch(self.branch)
        except VCSError as err:
            raise CFSConfigurationError(f'Failed to resolve branch {self.branch} '
                                        f'to commit hash: {err}')

        if not self.commit:
            raise CFSConfigurationError(f'Failed to resolve branch {self.branch} '
                                        f'to commit hash. No such branch.')

        # Clear out the branch so only commit hash is passed to CFS
        self.branch = None

    @property
    def req_payload(self):
        """Get the request payload to send to CFS for this layer.

        Returns:
            dict: the data for this layer in the format expected by the CFS API
        """
        req_payload = {}
        for cfs_prop, attr in self.CFS_PROPS_TO_ATTRS.items():
            value = getattr(self, attr, None)
            if value:
                req_payload[cfs_prop] = value
        return req_payload

    def __str__(self):
        return (f'layer with repo path {self.repo_path} and '
                f'{f"playbook {self.playbook}" if self.playbook else "default playbook"}')

    @staticmethod
    def construct_name(product_or_repo, playbook=None, commit=None, branch=None):
        """Construct a name for the layer following a naming convention.

        Args:
            product_or_repo (str): the name of the product or repository
            playbook (str, optional): the name of the playbook
            commit (str, optional): the commit hash
            branch (str, optional): the name of the branch. If both commit and branch
                are specified, branch is used in the name.

        Returns:
            str: the constructed layer name
        """
        playbook_name = os.path.splitext(playbook)[0] if playbook else 'site'
        name_components = [
            product_or_repo,
            playbook_name,
            branch or commit[:7],
            datetime.now().strftime('%Y%m%dT%H%M%S')
        ]
        return '-'.join(name_components)

    @classmethod
    def from_product_catalog(cls, product_name, product_version=None, name=None,
                             playbook=None, commit=None, branch=None):
        """Create a new CFSConfigurationLayer from product catalog data.

        Args:
            product_name (str): the name of the product in the product catalog
            product_version (str, optional): the version of the product in the
                product catalog. If omitted, the latest version is used.
            name (str, optional): an optional name override
            playbook (str, optional): the name of the Ansible playbook
            commit (str, optional): an optional commit override
            branch (str, optional): an optional branch override

        Returns:
            CFSConfigurationLayer: the layer constructed from the product

        Raises:
            CFSConfigurationError: if there is a problem getting required info
                from the product catalog to construct the layer.
        """
        fail_msg = (
            f'Failed to create CFS configuration layer for '
            f'{f"version {product_version} of " if product_version else ""}'
            f'product {product_name}'
        )

        try:
            product = ProductCatalog().get_product(product_name, product_version)
        except ProductCatalogError as err:
            raise CFSConfigurationError(f'{fail_msg}: {err}')

        if not product.clone_url:
            raise CFSConfigurationError(f'{fail_msg}: {product} has no clone URL.')
        else:
            clone_url = urlunparse(urlparse(product.clone_url)._replace(
                netloc=API_GW_HOST)
            )

        if not (commit or branch):
            if not product.commit:
                raise CFSConfigurationError(f'{fail_msg}: {product} has no commit hash.')
            commit = product.commit

        if not name:
            name = cls.construct_name(product_name, playbook=playbook,
                                      commit=commit, branch=branch)

        return CFSConfigurationLayer(clone_url, name=name, playbook=playbook,
                                     commit=commit, branch=branch)

    @classmethod
    def from_clone_url(cls, clone_url, name=None, playbook=None, commit=None, branch=None):
        """Create a new CFSConfigurationLayer from an explicit clone URL.

        Args:
            clone_url (str): the git repository clone URL
            name (str, optional): an optional name override
            playbook (str, optional): the name of the Ansible playbook
            commit (str, optional): an optional commit override
            branch (str, optional): an optional branch override

        Returns:
            CFSConfigurationLayer: the layer constructed from the product
        """
        def strip_suffix(s, suffix):
            if s.endswith(suffix):
                return s[:-len(suffix)]
            return s

        if not name:
            repo_name = os.path.basename(urlparse(clone_url).path)
            # Strip off the '.git' suffix then strip off '-config-management' if present
            short_repo_name = strip_suffix(strip_suffix(repo_name, '.git'), '-config-management')
            name = cls.construct_name(short_repo_name, playbook=playbook,
                                      commit=commit, branch=branch)

        return CFSConfigurationLayer(clone_url, name=name, playbook=playbook,
                                     commit=commit, branch=branch)

    @classmethod
    def from_cfs(cls, data):
        """Create a new CFSConfigurationLayer from data in a response from CFS.

        Args:
            data (dict): the data for the layer from CFS.
        """
        kwargs = {
            attr: data.get(cfs_prop)
            for cfs_prop, attr in cls.CFS_PROPS_TO_ATTRS.items()
        }
        return CFSConfigurationLayer(**kwargs)


class CFSConfiguration:
    """Represents a single configuration in CFS."""
    def __init__(self, cfs_client, data):
        self._cfs_client = cfs_client
        self.data = data
        self.layers = [CFSConfigurationLayer.from_cfs(layer_data)
                       for layer_data in self.data.get('layers', [])]
        self.changed = False

    @property
    def name(self):
        """str or None: the name of the CFS configuration"""
        return self.data.get('name')

    @property
    def req_payload(self):
        """dict: a dict containing just the layers key used to update in requests"""
        return {'layers': [layer.req_payload for layer in self.layers]}

    def save_to_cfs(self, name=None):
        """Save the configuration to CFS, optionally with a new name.

        Args:
            name (str or None): the name to save as. Required if this
                configuration does not yet have a name.

        Returns:
            CFSConfiguration: the new configuration that was saved to CFS

        Raises:
            CFSConfigurationError: if there is a failure saving the configuration
                to CFS.
        """
        if not name and not self.name:
            raise ValueError('A name must be specified for the CFS configuration.')
        name = name or self.name

        try:
            response_json = self._cfs_client.put('v2', 'configurations', name,
                                                 json=self.req_payload).json()
        except APIError as err:
            raise CFSConfigurationError(f'Failed to update CFS configuration "{self.name}": {err}')
        except ValueError as err:
            raise CFSConfigurationError(f'Failed to decode JSON response from updating '
                                        f'CFS configuration "{self.name}": {err}')

        LOGGER.info('Successfully saved CFS configuration "%s"', name)
        return CFSConfiguration(self._cfs_client, response_json)

    def save_to_file(self, file_path):
        """Save the configuration to a file.

        Args:
            file_path (str): the path to the file where this config should be saved

        Returns:
            None

        Raises:
            CFSConfigurationError: if there is a failure saving the configuration
                to the file.
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.req_payload, f, indent=2)
        except OSError as err:
            raise CFSConfigurationError(f'Failed to write to file file_path: {err}')

    def ensure_layer(self, layer, state=LayerState.PRESENT):
        """Ensure a layer exists or does not exist with the given parameters.

        Args:
            layer (CFSConfigurationLayer): the layer to ensure is present or
                absent
            state (LayerState): whether to ensure the layer is present or absent

        Returns:
            None
        """
        action = ('Removing', 'Updating')[state is LayerState.PRESENT]

        new_layers = []
        found_match = False
        for existing_layer in self.layers:
            if layer.matches(existing_layer):
                found_match = True
                LOGGER.info('%s existing %s', action, existing_layer)
                if state is LayerState.ABSENT:
                    # Skip adding this layer to new_layers
                    self.changed = True
                    continue

                updated_props = existing_layer.get_updated_values(layer)
                if updated_props:
                    self.changed = True
                    for updated_prop, update in updated_props.items():
                        LOGGER.info('Property "%s" of %s updated from %s to %s',
                                    updated_prop, existing_layer, update[0], update[1])
                new_layers.append(layer)
            else:
                # This layer doesn't match, so leave it untouched
                new_layers.append(existing_layer)

        if not found_match:
            LOGGER.info('No %s found.', layer)
            if state is LayerState.PRESENT:
                LOGGER.info('Adding a %s to the end.', layer)
                self.changed = True
                new_layers.append(layer)

        self.layers = new_layers

        if not self.changed:
            LOGGER.info('No changes to configuration "%s" are necessary.', self.name)
