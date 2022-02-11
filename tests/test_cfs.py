"""
Tests for the CFS client library.

(C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

from copy import deepcopy
import unittest
from unittest.mock import patch

from cfs_config_util.apiclient import APIError
from cfs_config_util.cfs import (
    CFSConfiguration,
    CFSConfigurationError,
    LayerState
)


class TestCFSConfiguration(unittest.TestCase):
    """Tests for the CFSConfiguration class."""
    def setUp(self):
        self.mock_cfs_client_cls = patch('cfs_config_util.cfs.CFSClient').start()
        self.mock_cfs_client = self.mock_cfs_client_cls.return_value
        self.mock_get_json = self.mock_cfs_client.get.return_value.json

        self.example_layer = {
            "cloneUrl": "https://api-gw-service-nmn.local/vcs/cray/example-config-management.git",
            "commit": "123456789abcdef",
            "name": "example-config",
            "playbook": "example-config.yml"
        }

        self.new_layer = {
            "cloneUrl": "https://api-gw-service-nmn.local/vcs/cray/new-config-management.git",
            "commit": "fedcba987654321",
            "name": "new-config",
            "playbook": "new-config.yml"
        }

        self.single_layer_config_data = {
            "lastUpdated": "2021-10-20T21:26:04Z",
            "layers": [
                deepcopy(self.example_layer)
            ],
            "name": "single-layer-config"
        }
        self.mock_get_json.return_value = self.single_layer_config_data
        self.mock_session = patch('cfs_config_util.cfs.AdminSession').start()

        self.duplicate_layer_config_data = {
            "lastUpdated": "2021-10-20T21:26:04Z",
            "layers": [
                deepcopy(self.example_layer),
                deepcopy(self.example_layer)
            ],
            "name": "config"
        }

    def tearDown(self):
        patch.stopall()

    def test_construct_cfs_configuration(self):
        """Test constructing a CFSConfiguration object."""
        cfs_config = CFSConfiguration('config')
        self.assertEqual(cfs_config.config, self.single_layer_config_data)

    def test_update_layers(self):
        """Test that update_layers properly calls the CFS API."""
        config_name = 'config'
        cfs_config = CFSConfiguration(config_name)
        layers = [self.example_layer, self.new_layer]
        new_update_time = '2022-02-11T14:45:01Z'
        self.mock_cfs_client.put.return_value.json.return_value = {
            'lastUpdated': new_update_time,
            'name': config_name,
            'layers': layers
        }

        cfs_config.update_layers(layers)

        self.mock_cfs_client.put.assert_called_once_with('v2', 'configurations', config_name,
                                                         json={'layers': layers})
        self.assertEqual(self.mock_cfs_client.put.return_value.json.return_value,
                         cfs_config.config)

    def test_update_layers_failure(self):
        """Test that update_layers raises an exception if the CFS API request fails."""
        self.mock_cfs_client.put.side_effect = APIError('cfs problem')
        cfs_config = CFSConfiguration('config')
        err_regex = f'Failed to update CFS configuration'

        with self.assertRaisesRegex(CFSConfigurationError, err_regex):
            cfs_config.update_layers([])

    def test_update_layers_bad_response_json(self):
        """Test that update_layers raises an exception if the CFS API gives bad JSON in response."""
        self.mock_cfs_client.put.return_value.json.side_effect = ValueError('bad json')
        cfs_config = CFSConfiguration('config')
        err_regex = f'Failed to decode JSON response from updating CFS configuration'

        with self.assertRaisesRegex(CFSConfigurationError, err_regex):
            cfs_config.update_layers([])

    def test_add_new_layer(self):
        """Test adding a new, totally different, layer to a CFSConfiguration"""
        cfs_config = CFSConfiguration('config')

        with patch.object(cfs_config, 'update_layers') as mock_update:
            cfs_config.ensure_layer(self.new_layer['name'],
                                    self.new_layer['commit'],
                                    self.new_layer['cloneUrl'],
                                    self.new_layer['playbook'],
                                    state=LayerState.PRESENT)

        mock_update.assert_called_once_with([self.example_layer, self.new_layer])

    def test_update_existing_layer(self):
        """Test updating an existing layer in a CFSConfiguration"""
        cfs_config = CFSConfiguration('config')
        new_commit_hash = 'fedcba987654321'
        expected_new_layer = deepcopy(self.example_layer)
        expected_new_layer['commit'] = new_commit_hash

        with patch.object(cfs_config, 'update_layers') as mock_update:
            cfs_config.ensure_layer(self.example_layer['name'],
                                    new_commit_hash,
                                    self.example_layer['cloneUrl'],
                                    self.example_layer['playbook'])

        mock_update.assert_called_once_with([expected_new_layer])

    def test_update_existing_layers(self):
        """Test updating two matching layers of a CFSConfiguration"""
        self.mock_get_json.return_value = self.duplicate_layer_config_data
        cfs_config = CFSConfiguration('config')
        new_commit_hash = 'fedcba987654321'
        expected_new_layer = deepcopy(self.example_layer)
        expected_new_layer['commit'] = new_commit_hash

        with patch.object(cfs_config, 'update_layers') as mock_update:
            cfs_config.ensure_layer(self.example_layer['name'],
                                    new_commit_hash,
                                    self.example_layer['cloneUrl'],
                                    self.example_layer['playbook'])

        mock_update.assert_called_once_with([expected_new_layer] * 2)

    def test_update_layer_no_changes(self):
        """Test updating a layer of the CFSConfiguration when nothing has changed."""
        cfs_config = CFSConfiguration('config')

        with patch.object(cfs_config, 'update_layers') as mock_update:
            cfs_config.ensure_layer(self.example_layer['name'],
                                    self.example_layer['commit'],
                                    self.example_layer['cloneUrl'],
                                    self.example_layer['playbook'])
        mock_update.assert_not_called()

    def test_remove_existing_layer(self):
        """Test removing a matching layer from a CFSConfiguration."""
        cfs_config = CFSConfiguration('config')

        with patch.object(cfs_config, 'update_layers') as mock_update:
            cfs_config.ensure_layer(self.example_layer['name'],
                                    self.example_layer['commit'],
                                    self.example_layer['cloneUrl'],
                                    self.example_layer['playbook'],
                                    state=LayerState.ABSENT)

        mock_update.assert_called_once_with([])

    def test_remove_existing_layers(self):
        """Test removing multiple matching layers from a CFSConfiguration."""
        multi_layer_config = deepcopy(self.duplicate_layer_config_data)
        multi_layer_config['layers'].append(self.new_layer)
        self.mock_get_json.return_value = multi_layer_config
        cfs_config = CFSConfiguration('config')

        with patch.object(cfs_config, 'update_layers') as mock_update:
            cfs_config.ensure_layer(self.example_layer['name'],
                                    self.example_layer['commit'],
                                    self.example_layer['cloneUrl'],
                                    self.example_layer['playbook'],
                                    state=LayerState.ABSENT)

        mock_update.assert_called_once_with([self.new_layer])

    def test_remove_non_existent_layer(self):
        """Test removing a layer that doesn't exist from a CFSConfiguration."""
        cfs_config = CFSConfiguration('config')

        with patch.object(cfs_config, 'update_layers') as mock_update:
            cfs_config.ensure_layer(self.example_layer['name'],
                                    self.example_layer['commit'],
                                    self.new_layer['cloneUrl'],
                                    self.new_layer['playbook'],
                                    state=LayerState.ABSENT)

        mock_update.assert_not_called()
