"""
Tests for cfs-config-util entry point parser.

Copyright 2022 Hewlett Packard Enterprise Development LP
"""
import argparse
import contextlib
import io
import itertools
import unittest
from unittest.mock import patch

from cfs_config_util.cfs import LayerState
from cfs_config_util.parser import check_args, create_parser, create_passthrough_parser


class TestParseAndCheckArgs(unittest.TestCase):
    """Tests for parse_args and check_args"""

    def setUp(self):
        """Create a parser to use in the tests."""
        self.parser = create_parser()

        self.product_layer_args = ['--product', 'sat:2.2.16']
        self.clone_url_branch_args = [
            '--clone-url', 'http://api-gw-service-nmn.local/vcs/cray/sat-config-management.git',
            '--git-branch', 'integration'
        ]
        self.clone_url_commit_args = self.clone_url_branch_args[:2] + ['--git-commit', '123abcd']
        self.layer_alternatives = [self.product_layer_args, self.clone_url_branch_args,
                                   self.clone_url_commit_args]

        self.base_config_args = ['--base-config', 'ncn-personalization']
        self.base_file_args = ['--base-file', 'ncn-personalization.json']
        self.base_query_args = ['--base-query', 'role=Management']
        self.base_alternatives = [self.base_config_args, self.base_file_args, self.base_query_args]

        self.save_args = ['--save']
        self.save_to_cfs_args = ['--save-to-cfs', 'ncn-personalization.new']
        self.save_to_file_args = ['--save-to-file', 'ncn-personalization-new.json']
        self.save_suffix_args = ['--save-suffix', '.new']
        self.save_alternatives = [self.save_args, self.save_to_cfs_args,
                                  self.save_to_file_args, self.save_suffix_args]

        self.missing_args_msg = 'one of the arguments .* is required'

    def assert_parse_error(self, args, err_regex=None):
        f = io.StringIO()
        with contextlib.redirect_stderr(f):
            with self.assertRaises(SystemExit) as err_cm:
                self.parser.parse_args(args)

        self.assertEqual(2, err_cm.exception.code)

        if err_regex:
            self.assertRegex(f.getvalue(), err_regex)

    def test_parse_and_check_combinations(self):
        """Test parsing args when given various combinations of args."""
        for layer_args, base_args, save_args in itertools.product(self.layer_alternatives,
                                                                  self.base_alternatives,
                                                                  self.save_alternatives):
            full_args = layer_args + base_args + save_args
            with self.subTest(full_args=full_args):
                # If using --base-query, then must use --save or --save-suffix
                valid_combo = (base_args != self.base_query_args
                               or save_args in [self.save_args, self.save_suffix_args])
                parsed_args = self.parser.parse_args(full_args)
                if valid_combo:
                    check_args(parsed_args)
                else:
                    with self.assertRaises(ValueError):
                        check_args(parsed_args)

    def test_parse_invalid_clone_url_layer(self):
        """Test parsing args when given a clone URL without a branch or commit hash."""
        parsed_args = self.parser.parse_args(self.clone_url_branch_args[:2] +
                                             self.base_config_args + self.save_args)
        with self.assertRaises(ValueError):
            check_args(parsed_args)

    def test_save_args_mutually_exclusive(self):
        """Test parsing raises error when given multiple mutually exclusive save options."""
        for mutex_args in itertools.combinations(self.save_alternatives, 2):
            full_args = self.base_config_args + self.product_layer_args
            full_args += itertools.chain.from_iterable(mutex_args)
            with self.subTest(full_args=full_args):
                self.assert_parse_error(full_args, 'not allowed with argument')

    def test_base_options_mutually_exclusive(self):
        """Test parsing raises error when given multiple mutually exclusive base options."""
        for mutex_args in itertools.combinations(self.base_alternatives, 2):
            full_args = self.product_layer_args + self.save_args
            full_args += itertools.chain.from_iterable(mutex_args)
            with self.subTest(full_args=full_args):
                self.assert_parse_error(full_args, 'not allowed with argument')

    def test_missing_layer_args(self):
        """Test parsing when missing an arg that defines the layer."""
        self.assert_parse_error(self.base_config_args + self.save_args,
                                self.missing_args_msg)

    def test_missing_base_args(self):
        """Test parsing when missing an argument specifying the base configuration or file."""
        self.assert_parse_error(self.product_layer_args + self.save_args,
                                self.missing_args_msg)

    def test_missing_save_args(self):
        """Test parsing when missing an argument specifying how the config should be saved."""
        self.assert_parse_error(self.product_layer_args + self.base_config_args,
                                self.missing_args_msg)

    def test_valid_state_args(self):
        """Test parsing with valid state args."""
        for arg_val, layer_state in [('present', LayerState.PRESENT), ('absent', LayerState.ABSENT)]:
            with self.subTest(state=arg_val):
                parsed_args = self.parser.parse_args(
                    self.product_layer_args + self.base_config_args + self.save_args +
                    ['--state', arg_val]
                )
                self.assertEqual(layer_state, parsed_args.state)

    def test_invalid_state_arg(self):
        """Test parsing with an invalid state arg."""
        full_args = self.product_layer_args + self.base_config_args + self.save_args + ['--state', 'gone']
        self.assert_parse_error(full_args, '--state: invalid')


class TestCreatePassthroughParser(unittest.TestCase):
    """Tests for the create_passthrough_parser function."""

    def setUp(self):
        self.mock_argument_parser_cls = patch('argparse.ArgumentParser').start()
        self.mock_argument_parser = self.mock_argument_parser_cls.return_value
        self.mock_add_git_options = patch('cfs_config_util.parser.add_git_options').start()
        self.mock_add_base_options = patch('cfs_config_util.parser.add_base_options').start()
        self.mock_add_save_options = patch('cfs_config_util.parser.add_save_options').start()

    def tearDown(self):
        patch.stopall()

    def test_create_passthrough_parser(self):
        """Test that only the desired passthrough options are added to the passthrough parser."""
        parser = create_passthrough_parser()

        self.mock_argument_parser_cls.assert_called_once_with(add_help=False,
                                                              usage=argparse.SUPPRESS,
                                                              allow_abbrev=False)
        self.mock_argument_parser.add_argument_group.assert_called_once_with(
            title='Git Options', description='Options that control the git ref used in the layer.'
        )
        self.mock_add_git_options.assert_called_once_with(
            self.mock_argument_parser.add_argument_group.return_value
        )
        self.mock_add_base_options.assert_called_once_with(self.mock_argument_parser)
        self.mock_add_save_options.assert_called_once_with(self.mock_argument_parser)


if __name__ == '__main__':
    unittest.main()
