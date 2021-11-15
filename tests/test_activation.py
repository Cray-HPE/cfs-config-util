"""
Tests for main activation automation.

Copyright (C) 2021 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

import unittest
from unittest.mock import MagicMock, patch

import cfs_config_util.activation
from cfs_config_util.activation import (
    cfs_activate_version,
    cfs_deactivate_version,
)
from cfs_config_util.cfs import CFSConfiguration


class TestActivation(unittest.TestCase):
    """Unit tests for activation automation."""
    def setUp(self):
        self.clone_url = "https://api-gw-service-nmn.local/foo/bar.git"
        self.product = "bar"
        self.version = "2.0.0"
        self.commit_hash = 'f1d2d2f924e986ac86fdf7b36c94bcdf32beec15'
        self.mock_get_commit_hash = patch.object(cfs_config_util.activation.VCSRepo, 'get_commit_hash_for_version',
                                                 return_value=self.commit_hash).start()
        self.layer_name = 'bar-ncn'
        self.playbook = 'bar.yml'

        self.mock_cfs_configuration = patch('cfs_config_util.activation.CFSConfiguration',
                                            autospec=CFSConfiguration).start()
        self.mock_cfs_configuration.get_configurations_for_components.return_value = [self.mock_cfs_configuration]
        self.cfg_name = 'bar'
        self.mock_cfs_configuration.name = self.cfg_name

    def tearDown(self):
        patch.stopall()

    def test_cfs_activate_version(self):
        """Test the cfs_activate_version() function when all configs succeed"""
        s, f = cfs_activate_version(self.product, self.version, self.layer_name, self.clone_url, self.playbook)
        self.mock_cfs_configuration.get_configurations_for_components.assert_called_once_with(
            role='Management',
            subrole='Master',
        )
        self.mock_cfs_configuration.ensure_layer.assert_called_once_with(
            self.layer_name,
            self.commit_hash,
            self.clone_url,
            self.playbook,
        )
        self.assertEqual(s, [self.cfg_name])

    def test_cfs_deactivate_version(self):
        """Test the cfs_deactivate_version() function when all configs succeed"""
        s, f = cfs_deactivate_version(self.layer_name)
        self.mock_cfs_configuration.get_configurations_for_components.assert_called_once_with(
            role='Management',
            subrole='Master',
        )
        self.mock_cfs_configuration.remove_layer.assert_called_once_with(self.layer_name)
        self.assertEqual(s, [self.cfg_name])
