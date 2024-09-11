#
# MIT License
#
# (C) Copyright 2021-2022, 2024 Hewlett Packard Enterprise Development LP
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
Tests for main activation automation.
"""
import logging
import unittest
from unittest.mock import Mock, patch

from csm_api_client.service.cfs import (
    CFSConfiguration,
    CFSConfigurationError,
    LayerState
)
from csm_api_client.service.gateway import APIError

from cfs_config_util.activation import (
    cfs_activate_version,
    cfs_deactivate_version,
    ensure_product_layer
)


class TestActivateDeactivate(unittest.TestCase):
    """Test the two main entry points cfs_activate_version and cfs_deactivate_version."""

    def setUp(self):
        self.product = 'sat'
        self.version = '2.2.16'
        self.playbook = 'sat-ncn.yml'
        self.hsm_query_params = {'Role': 'Management'}
        self.git_commit = '0123abc'
        self.git_branch = 'integration'
        self.mock_ensure_product_layer = patch('cfs_config_util.activation.ensure_product_layer').start()

    def tearDown(self):
        patch.stopall()

    def test_cfs_activate_version_no_git_ref(self):
        """Test cfs_activate_version without passing a git commit or branch."""
        ret_val = cfs_activate_version(self.product, self.version, self.playbook, self.hsm_query_params)
        self.assertEqual(self.mock_ensure_product_layer.return_value, ret_val)
        self.mock_ensure_product_layer.assert_called_once_with(
            self.product, self.version, self.playbook, LayerState.PRESENT, self.hsm_query_params,
            None, None, 'v3'
        )

    def test_cfs_activate_version_git_commit(self):
        """Test cfs_activate_version with a git commit."""
        ret_val = cfs_activate_version(self.product, self.version, self.playbook,
                                       self.hsm_query_params, git_commit=self.git_commit)
        self.assertEqual(self.mock_ensure_product_layer.return_value, ret_val)
        self.mock_ensure_product_layer.assert_called_once_with(
            self.product, self.version, self.playbook, LayerState.PRESENT, self.hsm_query_params,
            self.git_commit, None, 'v3'
        )

    def test_cfs_activate_version_git_branch(self):
        """Test cfs_activate_version with a git branch."""
        ret_val = cfs_activate_version(self.product, self.version, self.playbook,
                                       self.hsm_query_params, git_branch=self.git_branch)
        self.assertEqual(self.mock_ensure_product_layer.return_value, ret_val)
        self.mock_ensure_product_layer.assert_called_once_with(
            self.product, self.version, self.playbook, LayerState.PRESENT, self.hsm_query_params,
            None, self.git_branch, 'v3'
        )

    def test_cfs_deactivate_version_no_git_ref(self):
        """Test cfs_deactivate_version without passing a git commit or branch."""
        ret_val = cfs_deactivate_version(self.product, self.version, self.playbook, self.hsm_query_params)
        self.assertEqual(self.mock_ensure_product_layer.return_value, ret_val)
        self.mock_ensure_product_layer.assert_called_once_with(
            self.product, self.version, self.playbook, LayerState.ABSENT, self.hsm_query_params,
            None, None, 'v3'
        )

    def test_cfs_deactivate_version_git_commit(self):
        """Test cfs_activate_version with a git commit."""
        ret_val = cfs_deactivate_version(self.product, self.version, self.playbook,
                                         self.hsm_query_params, git_commit=self.git_commit)
        self.assertEqual(self.mock_ensure_product_layer.return_value, ret_val)
        self.mock_ensure_product_layer.assert_called_once_with(
            self.product, self.version, self.playbook, LayerState.ABSENT, self.hsm_query_params,
            self.git_commit, None, 'v3'
        )

    def test_cfs_deactivate_version_git_branch(self):
        """Test cfs_activate_version with a git branch."""
        ret_val = cfs_deactivate_version(self.product, self.version, self.playbook,
                                         self.hsm_query_params, git_branch=self.git_branch)
        self.assertEqual(self.mock_ensure_product_layer.return_value, ret_val)
        self.mock_ensure_product_layer.assert_called_once_with(
            self.product, self.version, self.playbook, LayerState.ABSENT, self.hsm_query_params,
            None, self.git_branch, 'v3'
        )


class TestEnsureProductLayer(unittest.TestCase):
    """Unit tests for ensure_product_layer function."""

    def setUp(self):
        self.product = 'sat'
        self.version = '2.2.16'
        self.playbook = 'sat-ncn.yml'
        self.state = LayerState.PRESENT
        self.hsm_query_params = {'Role': 'Management'}
        self.git_commit = '0123abc'
        self.git_branch = 'integration'

        self.mock_cfs_config_layer_cls = patch('cfs_config_util.activation.CFSConfigurationLayer').start()
        self.mock_cfs_config_layer = self.mock_cfs_config_layer_cls.from_product_catalog.return_value
        self.mock_admin_session = patch('cfs_config_util.activation.AdminSession').start()
        self.mock_hsm_client = patch('cfs_config_util.activation.HSMClient').start().return_value
        self.mock_cfs_client = patch('cfs_config_util.activation.CFSClientBase.get_cfs_client').start().return_value

        self.mock_cfs_config_names = ['ncn-personalization', 'ncn-personalization-storage']
        self.mock_cfs_configs = []
        for name in self.mock_cfs_config_names:
            mock_cfs_config = Mock(spec=CFSConfiguration)
            mock_cfs_config.name = name
            self.mock_cfs_configs.append(mock_cfs_config)
        self.mock_cfs_client.get_configurations_for_components.return_value = self.mock_cfs_configs

    def tearDown(self):
        patch.stopall()

    def test_ensure_product_layer_success(self):
        """Test ensure_product_layer works when it succeeds updating two configurations."""
        succeeded, failed = ensure_product_layer(
            self.product, self.version, self.playbook, self.state,
            self.hsm_query_params, git_commit=self.git_commit
        )
        self.assertEqual(self.mock_cfs_config_names, succeeded)
        self.assertEqual([], failed)

        self.mock_cfs_config_layer_cls.from_product_catalog.assert_called_once_with(
            self.product, self.version, playbook=self.playbook,
            commit=self.git_commit, branch=None
        )
        self.mock_cfs_client.get_configurations_for_components.assert_called_once_with(
            self.mock_hsm_client, **self.hsm_query_params
        )
        for config in self.mock_cfs_configs:
            config.ensure_layer.assert_called_once_with(self.mock_cfs_config_layer, self.state)
            config.save_to_cfs.assert_called_once_with()

    def test_ensure_product_layer_one_failure(self):
        """Test ensure_product_layer works when one config fails and one succeeds."""
        cfs_err = '503 Service Unavailable'
        self.mock_cfs_configs[0].save_to_cfs.side_effect = CFSConfigurationError(cfs_err)

        with self.assertLogs(level=logging.WARNING) as logs_cm:
            succeeded, failed = ensure_product_layer(
                self.product, self.version, self.playbook, self.state,
                self.hsm_query_params, git_branch=self.git_branch
            )

        self.assertEqual(
            logs_cm.records[0].message,
            f'Could not update CFS configuration {self.mock_cfs_config_names[0]}: {cfs_err}'
        )

        self.assertEqual(self.mock_cfs_config_names[1:], succeeded)
        self.assertEqual(self.mock_cfs_config_names[:1], failed)

        self.mock_cfs_config_layer_cls.from_product_catalog.assert_called_once_with(
            self.product, self.version, playbook=self.playbook,
            commit=None, branch=self.git_branch
        )
        self.mock_cfs_client.get_configurations_for_components.assert_called_once_with(
            self.mock_hsm_client, **self.hsm_query_params
        )
        for config in self.mock_cfs_configs:
            config.ensure_layer.assert_called_once_with(self.mock_cfs_config_layer, self.state)
            config.save_to_cfs.assert_called_once_with()

    def test_ensure_product_layer_empty_hsm_query(self):
        """Test that ensure_product_layer with empty HSM query params raises error."""
        err_regex = 'HSM query parameters must be specified'
        with self.assertRaisesRegex(CFSConfigurationError, err_regex):
            ensure_product_layer(self.product, self.version, self.playbook,
                                 self.state, {})

    def test_ensure_product_layer_get_config_failure(self):
        """Test that ensure_product_layer raises an exception when unable to find CFS configs."""
        cfs_err = '401 unauthorized'
        self.mock_cfs_client.get_configurations_for_components.side_effect = APIError(cfs_err)
        err_regex = f'Failed to query CFS or HSM for component configurations: {cfs_err}'

        with self.assertRaisesRegex(CFSConfigurationError, err_regex):
            ensure_product_layer(
                self.product, self.version, self.playbook, self.state,
                self.hsm_query_params
            )
