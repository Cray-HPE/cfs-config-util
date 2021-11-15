"""
Tests for the CFS client library.

(C) Copyright 2021 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

from cfs_config_util.cfs import CFSConfiguration, CFSConfigurationError


class TestCFSConfiguration(unittest.TestCase):
    """Tests for the CFSConfiguration class."""
    def setUp(self):
        self.mock_cfs_client = patch('cfs_config_util.cfs.CFSClient').start()
        self.config_payload = {
            "lastUpdated": "2021-10-20T21:26:04Z",
            "layers": [
                {
                    "cloneUrl": "https://api-gw-service-nmn.local/vcs/cray/some-configuration.git",
                    "commit": "123456789abcdef",
                    "name": "some-config",
                    "playbook": "some-config.yml"
                }
            ],
            "name": "config"
        }
        self.mock_cfs_client.return_value.get.return_value.json.return_value = self.config_payload
        self.mock_session = patch('cfs_config_util.cfs.AdminSession').start()

        self.payload_with_duplicate_names = {
            "lastUpdated": "2021-10-20T21:26:04Z",
            "layers": [
                {
                    "cloneUrl": "https://api-gw-service-nmn.local/vcs/cray/some-configuration.git",
                    "commit": "123456789abcdef",
                    "name": "some-config",
                    "playbook": "some-config.yml"
                },
            ] * 3,
            "name": "config"
        }

    def tearDown(self):
        patch.stopall()

    def test_construct_cfs_configuration(self):
        """Test constructing a CFSConfiguration object."""
        cfs_config = CFSConfiguration('config')
        self.assertEqual(cfs_config.config, self.config_payload)

    def test_add_new_layer(self):
        """Test adding a new layer to a CFSConfiguration"""
        cfs_config = CFSConfiguration('config')
        cfg_layers = len(cfs_config.layers)
        cfs_config.ensure_layer('some-new-config', 'fedcba987654321',
                                'https://api-gw-service-nmn.local/vcs/cray/some-new-configuration.git',
                                'some-new-config.yml')
        self.assertEqual(len(cfs_config.layers), cfg_layers + 1)
        self.mock_cfs_client.return_value.put.assert_called_once()

    def test_update_existing_layer(self):
        """Test that updating existing layers maintains idempotency"""
        new_commit_hash = 'fedcba987654321'
        new_url = 'https://api-gw-service-nmn.local/vcs/cray/some-updated-configuration.git'
        new_playbook = 'some-updated-config.yml'

        cfs_config = CFSConfiguration('config')
        cfg_layers = len(cfs_config.layers)
        cfs_config.ensure_layer('some-config', new_commit_hash, new_url, new_playbook)
        self.assertEqual(len(cfs_config.layers), cfg_layers)
        self.mock_cfs_client.return_value.put.assert_called_once()

        for key, updated_value in [('commit', new_commit_hash),
                                   ('cloneUrl', new_url),
                                   ('playbook', new_playbook)]:
            self.assertEqual(cfs_config.config['layers'][0][key], updated_value)

    def test_no_exit_with_no_duplicates(self):
        """Test that the program does not exit when layer names are unique."""
        try:
            CFSConfiguration('config').check_duplicate_layer_names('some-config')
        except SystemExit:
            self.fail('program exited but no duplicate layer names were present.')

    def test_exit_on_duplicates(self):
        """Test that the program exits when duplicate layer names are detected."""
        self.mock_cfs_client.return_value.get.return_value.json.return_value = self.payload_with_duplicate_names
        with self.assertRaises(CFSConfigurationError):
            CFSConfiguration('config').check_duplicate_layer_names('some-config')

    def test_ensure_layer_checks_for_duplicates(self):
        """Test that ensure_layer checks for duplicates."""
        cfs_config = CFSConfiguration('config')
        with patch('cfs_config_util.cfs.CFSConfiguration.check_duplicate_layer_names') as mock_exit:
            cfs_config.ensure_layer('some-new-config', 'fedcba987654321',
                                    'https://api-gw-service-nmn.local/vcs/cray/some-new-configuration.git',
                                    'some-new-config.yml')
        mock_exit.assert_called_once()

    def test_ensure_layer_checks_for_duplicates(self):
        """Test that ensure_layer checks for duplicates."""
        cfs_config = CFSConfiguration('config')
        with patch('cfs_config_util.cfs.CFSConfiguration.check_duplicate_layer_names') as mock_exit:
            cfs_config.remove_layer('some-new-config')
        mock_exit.assert_called_once()

    def test_remove_layer_removes_layer(self):
        """Test that remove_layer will remove a layer with the given name."""
        cfs_config = CFSConfiguration('config')
        cfs_config.remove_layer('some-config')
        self.assertEqual(cfs_config.layers, [])
        self.mock_cfs_client.return_value.put.assert_called_once()

    def test_removing_nonexistent_layer_warns_user(self):
        """Test that removing a non-existent layer logs a warning message."""
        cfs_config = CFSConfiguration('config')
        starting_layers = cfs_config.layers
        with self.assertLogs(level='WARN'):
            cfs_config.remove_layer('nonexistent-layer')

    def test_removing_nonexistent_layer_is_noop(self):
        """Test that removing a non-existent layer does nothing."""
        cfs_config = CFSConfiguration('config')
        starting_layers = cfs_config.layers
        cfs_config.remove_layer('nonexistent-layer')
        self.assertEqual(cfs_config.layers, starting_layers)
