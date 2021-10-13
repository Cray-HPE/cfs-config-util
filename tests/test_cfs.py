"""
Tests for the CFS client library.

(C) Copyright 2021 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

from cfs_config_util.cfs import CFSConfiguration


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
        cfg_layers = len(cfs_config.config.get('layers'))
        cfs_config.update_layer('some-new-config', 'fedcba987654321',
                                'https://api-gw-service-nmn.local/vcs/cray/some-new-configuration.git',
                                'some-new-config.yml')
        self.assertEqual(len(cfs_config.config.get('layers')), cfg_layers + 1)
        self.mock_cfs_client.return_value.put.assert_called_once()

    def test_update_existing_layer(self):
        """Test that updating existing layers maintains idempotency"""
        new_commit_hash = 'fedcba987654321'
        new_url = 'https://api-gw-service-nmn.local/vcs/cray/some-updated-configuration.git'
        new_playbook = 'some-updated-config.yml'

        cfs_config = CFSConfiguration('config')
        cfg_layers = len(cfs_config.config.get('layers'))
        cfs_config.update_layer('some-config', new_commit_hash, new_url, new_playbook)
        self.assertEqual(len(cfs_config.config.get('layers')), cfg_layers)
        self.mock_cfs_client.return_value.put.assert_called_once()

        for key, updated_value in [('commit', new_commit_hash),
                                   ('cloneUrl', new_url),
                                   ('playbook', new_playbook)]:
            self.assertEqual(cfs_config.config['layers'][0][key], updated_value)

    def test_detecting_duplicate_layers(self):
        """Test that layers with duplicate names are detected."""
        duplicates = list(CFSConfiguration.find_duplicate_layers(self.payload_with_duplicate_names['layers']))
        self.assertEqual(duplicates, ['some-config'])

    def test_exit_on_duplicates(self):
        """Test that the program exits when duplicate layer names are detected."""
        self.mock_cfs_client.return_value.get.return_value.json.return_value = self.payload_with_duplicate_names
        with self.assertRaises(SystemExit):
            CFSConfiguration('config').update_layer(
                'some-config',
                '123456789abcdef',
                'https://api-gw-service-nmn.local/vcs/cray/some-updated-configuration.git',
                'sat-ncn.yml'
            )
