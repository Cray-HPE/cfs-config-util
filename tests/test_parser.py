#
# MIT License
#
# (C) Copyright 2022-2023 Hewlett Packard Enterprise Development LP
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
Tests for cfs-config-util entry point parser.
"""
import argparse
import contextlib
import io
import itertools
import unittest
from unittest.mock import patch

from csm_api_client.service.cfs import LayerState

from cfs_config_util.parser import check_args, convert_query_to_dict, create_parser, create_passthrough_parser


class TestConvertQueryToDict(unittest.TestCase):

    def test_single_key_value(self):
        """Test convert_query_to_dict on a single 'key=value' pair"""
        converted = convert_query_to_dict('role=management')
        self.assertEqual({'role': ['management']}, converted)

    def test_multiple_key_value(self):
        """Test convert_query_to_dict on multiple 'key=value' pairs"""
        converted = convert_query_to_dict('role=management,subrole=storage')
        self.assertEqual({'role': ['management'], 'subrole': ['storage']}, converted)

    def test_multiple_key_value_with_repeats(self):
        """Test convert_query_to_dict on multiple 'key=value' pairs with a repeated key"""
        converted = convert_query_to_dict('role=management,subrole=storage,subrole=master')
        self.assertEqual({'role': ['management'], 'subrole': ['storage', 'master']}, converted)


class TestParseArgsBase(unittest.TestCase):
    """Base class for argument parsing tests"""
    def assert_parse_error(self, args, err_regex=None):
        f = io.StringIO()
        with contextlib.redirect_stderr(f):
            with self.assertRaises(SystemExit) as err_cm:
                self.parser.parse_args(args)

        self.assertEqual(2, err_cm.exception.code)

        if err_regex:
            self.assertRegex(f.getvalue(), err_regex)


class TestUpdateConfigParseAndCheckArgs(TestParseArgsBase):
    """Tests for parse_args and check_args with update-config action."""

    def setUp(self):
        """Create a parser to use in the tests."""
        self.parser = create_parser()

        self.action_args = ['update-config']

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

        self.assign_to_xnames_args = ['--assign-to-xnames', 'x3000c0s1b0n0,x3000c0s3b0n0']
        self.assign_to_query_args = ['--assign-to-query', 'role=management,subrole=master']
        # These two assign options are not mutually exclusive
        self.assign_alternatives = [self.assign_to_xnames_args, self.assign_to_query_args,
                                    self.assign_to_xnames_args + self.assign_to_query_args]

        self.clear_state_args = ['--clear-state']
        self.clear_error_args = ['--clear-error']
        self.enable_args = ['--enable']
        self.disable_args = ['--disable']
        self.apply_alternatives = [
            self.clear_state_args + self.clear_error_args + self.enable_args,
            self.clear_state_args + self.clear_error_args + self.disable_args,
            self.clear_state_args + self.enable_args,
            self.clear_state_args + self.disable_args,
            self.clear_error_args + self.enable_args,
            self.clear_error_args + self.disable_args,
            self.enable_args,
            self.disable_args
        ]

        self.missing_args_msg = 'one of the arguments .* is required'

    def test_parse_and_check_combinations(self):
        """Test parsing args when given various combinations of args."""
        for layer_args, base_args, save_args in itertools.product(self.layer_alternatives,
                                                                  self.base_alternatives + [[]],
                                                                  self.save_alternatives):
            full_args = self.action_args + layer_args + base_args + save_args
            with self.subTest(full_args=full_args):
                # If using --base-query, then must use --save or --save-suffix.
                # If not using any --base*, cannot use --save or --save-suffix.
                valid_combo = (not (base_args == self.base_query_args
                                    and save_args in [self.save_to_cfs_args, self.save_to_file_args])
                               and (base_args or save_args not in [self.save_args, self.save_suffix_args]))

                parsed_args = self.parser.parse_args(full_args)
                if valid_combo:
                    check_args(parsed_args)
                else:
                    with self.assertRaises(ValueError):
                        check_args(parsed_args)

    def test_parse_invalid_clone_url_layer(self):
        """Test parsing args when given a clone URL without a branch or commit hash."""
        parsed_args = self.parser.parse_args(self.action_args + self.clone_url_branch_args[:2] +
                                             self.base_config_args + self.save_args)
        with self.assertRaises(ValueError):
            check_args(parsed_args)

    def test_save_args_mutually_exclusive(self):
        """Test parsing raises error when given multiple mutually exclusive save options."""
        for mutex_args in itertools.combinations(self.save_alternatives, 2):
            full_args = self.action_args + self.base_config_args + self.product_layer_args
            full_args += itertools.chain.from_iterable(mutex_args)
            with self.subTest(full_args=full_args):
                self.assert_parse_error(full_args, 'not allowed with argument')

    def test_base_options_mutually_exclusive(self):
        """Test parsing raises error when given multiple mutually exclusive base options."""
        for mutex_args in itertools.combinations(self.base_alternatives, 2):
            full_args = self.action_args + self.product_layer_args + self.save_args
            full_args += itertools.chain.from_iterable(mutex_args)
            with self.subTest(full_args=full_args):
                self.assert_parse_error(full_args, 'not allowed with argument')

    def test_missing_layer_args(self):
        """Test parsing when missing an arg that defines the layer."""
        self.assert_parse_error(self.action_args + self.base_config_args + self.save_args,
                                self.missing_args_msg)

    def test_missing_save_args(self):
        """Test parsing when missing an argument specifying how the config should be saved."""
        self.assert_parse_error(self.action_args + self.product_layer_args + self.base_config_args,
                                self.missing_args_msg)

    def test_valid_state_args(self):
        """Test parsing with valid state args."""
        for arg_val, layer_state in [('present', LayerState.PRESENT), ('absent', LayerState.ABSENT)]:
            with self.subTest(state=arg_val):
                parsed_args = self.parser.parse_args(
                    self.action_args + self.product_layer_args + self.base_config_args + self.save_args +
                    ['--state', arg_val]
                )
                self.assertEqual(layer_state, parsed_args.state)

    def test_invalid_state_arg(self):
        """Test parsing with an invalid state arg."""
        full_args = self.action_args + self.product_layer_args + \
            self.base_config_args + self.save_args + ['--state', 'gone']
        self.assert_parse_error(full_args, '--state: invalid')

    def test_valid_assign_arg_combos(self):
        """Test parsing with valid --assign-to-args and --assign-to-query arguments"""
        valid_combos = [
            # Start from a base CFS configuration and save in-place
            self.base_config_args + self.save_args,
            # Start from a base CFS configuration and save with a suffix
            self.base_config_args + self.save_suffix_args,
            # Start from a base CFS configuration and save to a new CFS configuration
            self.base_config_args + self.save_to_cfs_args,
            # Start from a base file and save to CFS
            self.base_file_args + self.save_to_cfs_args,
        ]

        for layer_args in self.layer_alternatives:
            for assign_args in self.assign_alternatives:
                for arg_combo in valid_combos:
                    full_args = self.action_args + layer_args + arg_combo + assign_args
                    with self.subTest(full_args=full_args):
                        parsed_args = self.parser.parse_args(full_args)
                        check_args(parsed_args)

    def test_invalid_assign_arg_not_saved_to_cfs(self):
        """Test parsing with invalid --assign* specified when not saving to CFS"""
        # All these invalid combinations save to a file, which cannot then be
        # assigned to a CFS component
        invalid_combos = [
            # Start from a base CFS configuration and save to a file
            self.base_config_args + self.save_to_file_args,
            # Start from a base file and save in place
            self.base_file_args + self.save_args,
            # Start from a base file and save to a new file
            self.base_file_args + self.save_to_file_args,
            # Start from a base file and save to a file with a suffix
            self.base_file_args + self.save_suffix_args,
        ]
        expected_err_regex = (
            'The --assign-to-xnames or --assign-to-query options require the '
            'resulting CFS configuration to be saved to CFS.'
        )

        for layer_args, assign_args, arg_combo in itertools.product(self.layer_alternatives,
                                                                    self.assign_alternatives,
                                                                    invalid_combos):
            full_args = self.action_args + layer_args + arg_combo + assign_args
            with self.subTest(full_args=full_args):
                parsed_args = self.parser.parse_args(full_args)
                with self.assertRaisesRegex(ValueError, expected_err_regex):
                    check_args(parsed_args)

    def test_invalid_assign_arg_with_base_query(self):
        """Test parsing with invalid --assign* specified with --base-query"""
        # Both these combinations use --base-query, which can match more than
        # one CFS configuration, which means they can't both be assigned to components
        invalid_combos = [
            # Start from a base query and save in place
            self.base_query_args + self.save_args,
            # Start from a base query and save with a suffix
            self.base_query_args + self.save_suffix_args
        ]
        expected_err_regex = (
            '--base-query is not compatible with --assign-to-query or --assign-to-xnames'
        )

        for layer_args, assign_args, arg_combo in itertools.product(self.layer_alternatives,
                                                                    self.assign_alternatives,
                                                                    invalid_combos):
            full_args = self.action_args + layer_args + arg_combo + assign_args
            with self.subTest(full_args=full_args):
                parsed_args = self.parser.parse_args(full_args)
                with self.assertRaisesRegex(ValueError, expected_err_regex):
                    check_args(parsed_args)

    def test_valid_apply_args_no_assign(self):
        """Test parsing with valid apply arguments without assignment"""
        valid_combos = [
            self.base_query_args + self.save_args,
            self.base_query_args + self.save_suffix_args,
            self.base_config_args + self.save_args,
            self.base_config_args + self.save_suffix_args,
            self.base_config_args + self.save_to_cfs_args,
            self.base_file_args + self.save_to_cfs_args,
        ]
        for layer_args, arg_combo, apply_args in itertools.product(self.layer_alternatives,
                                                                   valid_combos,
                                                                   self.apply_alternatives):
            full_args = self.action_args + layer_args + arg_combo + apply_args
            with self.subTest(full_args=full_args):
                parsed_args = self.parser.parse_args(full_args)
                check_args(parsed_args)

    def test_valid_apply_args_with_assign(self):
        """Test parsing with valid apply arguments with assignment"""
        valid_combos = [
            self.base_config_args + self.save_args,
            self.base_config_args + self.save_suffix_args,
            self.base_config_args + self.save_to_cfs_args,
            self.base_file_args + self.save_to_cfs_args,
        ]
        for layer_args, assign_args, arg_combo, apply_args in itertools.product(self.layer_alternatives,
                                                                                self.assign_alternatives,
                                                                                valid_combos,
                                                                                self.apply_alternatives):
            full_args = self.action_args + layer_args + arg_combo + assign_args + apply_args
            with self.subTest(full_args=full_args):
                parsed_args = self.parser.parse_args(full_args)
                check_args(parsed_args)

    def test_invalid_apply_args_not_saved_to_cfs(self):
        """Test parsing with invalid apply args specified without saving to CFS"""
        invalid_combos = [
            self.base_config_args + self.save_to_file_args,
            self.base_file_args + self.save_to_file_args,
            self.base_file_args + self.save_args,
            self.base_file_args + self.save_suffix_args
        ]
        expected_err_regex = (
            'The options --clear-state, --clear-error, --enable, or --disable '
            'require the resulting CFS configuration be saved to CFS.'
        )

        for layer_args, arg_combo, apply_args in itertools.product(self.layer_alternatives,
                                                                   invalid_combos,
                                                                   self.apply_alternatives):
            full_args = self.action_args + layer_args + arg_combo + apply_args
            with self.subTest(full_args=full_args):
                parsed_args = self.parser.parse_args(full_args)
                with self.assertRaisesRegex(ValueError, expected_err_regex):
                    check_args(parsed_args)

    def test_enable_disable_mutually_exclusive(self):
        """Test parsing raises error when given mutually exclusive --enable/--disable options"""
        full_args = (
                self.action_args + self.product_layer_args + self.base_config_args +
                self.save_args + self.enable_args + self.disable_args
        )
        self.assert_parse_error(full_args, 'argument --disable: not allowed with argument --enable')


class TestCreatePassthroughParser(unittest.TestCase):
    """Tests for the create_passthrough_parser function."""

    def setUp(self):
        self.mock_argument_parser_cls = patch('argparse.ArgumentParser').start()
        self.mock_argument_parser = self.mock_argument_parser_cls.return_value
        self.mock_add_git_options = patch('cfs_config_util.parser.add_git_options').start()
        self.mock_add_base_options = patch('cfs_config_util.parser.add_base_options').start()
        self.mock_add_save_options = patch('cfs_config_util.parser.add_save_options').start()
        self.mock_add_assign_options = patch('cfs_config_util.parser.add_assign_options').start()

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
        self.mock_add_assign_options.assert_called_once_with(self.mock_argument_parser)


if __name__ == '__main__':
    unittest.main()
