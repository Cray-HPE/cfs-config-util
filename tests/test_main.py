#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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
Tests for the cfs_config_util.main module.
"""

from argparse import Namespace
import unittest
from unittest.mock import patch


from cfs_config_util.bin.main import construct_layers


class TestConstructLayers(unittest.TestCase):
    """Tests for the construct_layers() function"""

    def setUp(self):
        self.layer_name = 'test_layer'
        self.playbook_name = 'test.yml'
        self.product_name = 'product'

        self.args = Namespace(
            layer_name=self.layer_name,
            playbooks=[self.playbook_name],
            product=self.product_name,
            git_commit=None,
            git_branch=None,
        )

        patcher = patch('cfs_config_util.bin.main.CFSConfigurationLayer')
        self.mock_cfs_configuration_layer = patcher.start()

    def tearDown(self):
        patch.stopall()

    def test_single_layer_constructed(self):
        """Test constructing a single layer for a product"""
        construct_layers(self.args)
        self.mock_cfs_configuration_layer.from_product_catalog.assert_called_once_with(
            self.product_name,
            product_version=None,
            name=self.layer_name,
            playbook=self.playbook_name,
            commit=None,
            branch=None,
        )

    def test_single_default_layer_constructed_for_no_playbook(self):
        """Test that a default layer is constructed when no playbook is given"""
        self.args.playbooks = None
        construct_layers(self.args)
        self.mock_cfs_configuration_layer.from_product_catalog.assert_called_once_with(
            self.product_name,
            product_version=None,
            name=self.layer_name,
            playbook=None,
            commit=None,
            branch=None,
        )

    def test_multiple_playbook_layers_constructed(self):
        """Test constructing multiple layers for a product with multiple playbooks"""
        additional_playbook = 'additional.yml'
        playbooks = [self.playbook_name, additional_playbook]
        self.args.playbooks = playbooks

        construct_layers(self.args)

        for playbook in playbooks:
            self.mock_cfs_configuration_layer.from_product_catalog.assert_any_call(
                self.product_name,
                product_version=None,
                name=self.layer_name,
                playbook=playbook,
                commit=None,
                branch=None,
            )
