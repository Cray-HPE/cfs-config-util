"""
Basic client library for CFS.

(C) Copyright 2021 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

from collections import Counter
from copy import deepcopy
import json
import logging
import os
import subprocess
from urllib.parse import ParseResult, urlunparse

from cfs_config_util.apiclient import APIError, CFSClient, HSMClient
from cfs_config_util.session import AdminSession


LOGGER = logging.getLogger(__name__)


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
            LOGGER.error('Could not access CFS: %s', err)
            raise SystemExit(1)
        except json.JSONDecodeError as err:
            LOGGER.error('Invalid JSON response received from CFS: %s', err)
            raise SystemExit(1)

    def update_layer(self, layer_name, commit_hash, clone_url, playbook):
        """Ensures a layer exists with the given parameters.

        Args:
            layer_name (str): the name of the layer
            commit_hash (str): the commit hash of the configuration to use in
                VCS
            clone_url (str): the URL in VCS containing the configuration
            playbook (str): the path to the playbook in the VCS repo

        Returns: None.

        Raises:
            APIError: if there is an issue querying CFS.
        """
        layers = deepcopy(self.config.get('layers'))

        new_layer_base = {
            'commit': commit_hash,
            'cloneUrl': clone_url,
            'playbook': playbook,
        }

        # TODO: Exiting here may not be the best general solution. See
        # CRAYSAT-1221.
        duplicate_layers = set(self.find_duplicate_layers(layers))
        if layer_name in duplicate_layers:
            LOGGER.error('Duplicate layers with name "%s" found in configuration "%s"; exiting.',
                         layer_name, self.name)
            raise SystemExit(1)

        for layer in layers:
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
            layers.append(new_layer)

        new_config = {'layers': layers}
        self._cfs_client.put('v2', 'configurations', self.name, json=new_config)
        self.config.update(new_config)
        LOGGER.info('Successfully updated layer "%s" in configuration "%s"',
                    layer_name, self.name)

    @staticmethod
    def find_duplicate_layers(layers):
        """Search for duplicate layers in a list of layers.

        Args:
            layers ([dict]): the layers in the configuration returned from CFS.

        Returns:
            set: names which refer to more than one layer in the configuration.
        """
        counts_by_name = Counter([layer.get('name') for layer in layers])
        return set(layer_name for layer_name, count in counts_by_name.items()
                   if count > 1)


def get_remote_refs(vcs_username, vcs_host, vcs_path):
    """Get the remote refs for a remote repo.

    Args:
        vcs_username (str): username to authenticate to git server
        vcs_host (str): the hostname of the git server
        vcs_path (str): the path to the repository on the server

    Returns:
        dict: mapping of remote refs to their corresponding commit hashes
    """

    user_netloc = f'{vcs_username}@{vcs_host}'
    url_components = ParseResult(scheme='https', netloc=user_netloc, path=vcs_path,
                                 params='', query='', fragment='')
    vcs_full_url = urlunparse(url_components)

    # Get the password directly from k8s to avoid leaking it via the /proc
    # filesystem.
    env = dict(**os.environ, GIT_ASKPASS='vcs-creds-helper')
    proc = subprocess.run(['git', 'ls-remote', vcs_full_url],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, check=True)

    # Each line in the output from `git ls-remote` has the form
    # "<commit_hash>\t<ref_name>", and we want the returned dictionary to map
    # the other way, i.e. from ref names to commit hashes. Thus when we split
    # each line on '\t', we should reverse the order of the resulting pair
    # before inserting it into the dictionary (hence the `reversed` in the
    # following comprehension.)
    return dict(
        tuple(reversed(line.split('\t')))
        for line in proc.stdout.decode('utf-8').split('\n')
        if line
    )


def get_cfs_configurations():
    """Get a list of CFS configurations for the manager NCNs.

    Returns:
        set[str]: names of the CFS configurations in use on the
            manager NCNs.
    """
    session = AdminSession.get_session()
    hsm_client = HSMClient(session)
    cfs_client = CFSClient(session)

    try:
        mgr_xnames = hsm_client.get_component_xnames(params={'Role': 'Management', 'Subrole': 'Master'})
    except APIError as err:
        LOGGER.error('Could not retrieve manager NCN xnames from HSM: %s', err)
        raise SystemExit(1)

    LOGGER.info('Querying CFS configurations for the following NCNs: %s',
                ', '.join(mgr_xnames))

    try:
        desired_configs = set(cfs_client.get('v2', 'components', ncn).json().get('desiredConfig') for ncn in mgr_xnames)
        LOGGER.info('Found the following configurations for NCNs: %s',
                    ', '.join(desired_configs))
        return desired_configs
    except APIError as err:
        LOGGER.error('Could not retrieve CFS configurations for manager NCNs: %s', err)
        raise SystemExit(1)
