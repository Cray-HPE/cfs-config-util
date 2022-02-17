"""
Tests for main activation automation.

Copyright (C) 2021-2022 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

import unittest
from unittest.mock import Mock, patch

from cfs_config_util.activation import (
    VCSRepo,
    cfs_activate_version,
    cfs_deactivate_version,
    ensure_product_layer
)
from cfs_config_util.cfs import (
    CFSConfiguration,
    CFSConfigurationError,
    LayerState
)


class TestActivation(unittest.TestCase):
    """Unit tests for top-level functions for activating verison of products in CFS configurations"""
    def setUp(self):
        self.clone_url = "https://api-gw-service-nmn.local/foo/bar.git"
        self.product = "bar"
        self.version = "2.0.0"
        self.commit_hash = 'f1d2d2f924e986ac86fdf7b36c94bcdf32beec15'
        self.mock_get_commit_hash = patch.object(VCSRepo, 'get_commit_hash_for_version',
                                                 return_value=self.commit_hash).start()
        self.playbook = 'bar.yml'

        self.mock_cfs_configuration = Mock()
        self.cfg_name = 'bar'
        self.mock_cfs_configuration.name = self.cfg_name
        self.mock_cfs_configuration_cls = patch('cfs_config_util.activation.CFSConfiguration',
                                                autospec=CFSConfiguration).start()
        self.mock_cfs_configuration_cls.get_configurations_for_components.return_value = [self.mock_cfs_configuration]

    def tearDown(self):
        patch.stopall()

    def test_ensure_product_layer(self):
        """Test ensure_product_layer successful case."""
        state = 'present'
        s, f = ensure_product_layer(self.product, self.version, self.clone_url, self.playbook, state)
        self.mock_cfs_configuration_cls.get_configurations_for_components.assert_called_once_with(
            role='Management',
            subrole='Master'
        )
        self.mock_cfs_configuration.ensure_layer.assert_called_once_with(
            f'{self.product}-{self.version}', self.commit_hash,
            self.clone_url, self.playbook, state=state
        )
        self.assertEqual([self.cfg_name], s)

    def test_ensure_product_layer_one_failure(self):
        """Test ensure_product_layer when one configuration fails and one succeeds."""
        success_config = Mock()
        success_config.name = 'success'
        failure_config = Mock()
        failure_config.name = 'failure'
        failure_config.ensure_layer.side_effect = CFSConfigurationError()
        self.mock_cfs_configuration_cls.get_configurations_for_components.return_value = [
            failure_config, success_config
        ]
        state = 'present'

        s, f = ensure_product_layer(self.product, self.version, self.clone_url, self.playbook, state)
        self.mock_cfs_configuration_cls.get_configurations_for_components.assert_called_once_with(
            role='Management',
            subrole='Master'
        )
        self.assertEqual([success_config.name], s)
        self.assertEqual([failure_config.name], f)

    @patch('cfs_config_util.activation.ensure_product_layer')
    def test_cfs_activate_version(self, mock_ensure):
        """Test the cfs_activate_version properly calls ensure_product_layer"""
        result = cfs_activate_version(self.product, self.version, self.clone_url, self.playbook)
        self.assertEqual(mock_ensure.return_value, result)
        mock_ensure.assert_called_once_with(self.product, self.version, self.clone_url,
                                            self.playbook, LayerState.PRESENT)

    @patch('cfs_config_util.activation.ensure_product_layer')
    def test_cfs_deactivate_version(self, mock_ensure):
        """Test the cfs_deactivate_version properly calls ensure_product_layer"""
        result = cfs_deactivate_version(self.product, self.version, self.clone_url, self.playbook)
        self.assertEqual(mock_ensure.return_value, result)
        mock_ensure.assert_called_once_with(self.product, self.version, self.clone_url,
                                            self.playbook, LayerState.ABSENT)
