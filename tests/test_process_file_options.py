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
Tests for process_file_options module.
"""
import unittest

from cfs_config_util.bin.process_file_options import process_file_options, INPUT_DATA_DIR, OUTPUT_DATA_DIR


class TestProcessFileOptions(unittest.TestCase):
    """Test for the process_file_options function."""

    def setUp(self):
        self.common_args = ['--product', 'sat', '--playbook', 'sat-ncn.yml']
        self.common_args_string = ' '.join(self.common_args)
        self.base_file_name = 'ncn-personalization.json'
        self.save_file_name = 'updated-ncn-personalization.json'

    @staticmethod
    def get_bind_mount_str(src, target, readonly=False):
        """Get an expected bind mount string.

        Args:
            src (str): the source of the bind mount
            target (str): the target of the bind mount
            readonly (bool): whether it's a read-only mount or not
        """
        bind_mount_str = f'--mount type=bind,src={src},target={target}'
        if readonly:
            bind_mount_str += ',ro=true'
        return bind_mount_str

    def test_base_file_absolute_path_save_in_place(self):
        """Test with a --base-file specifying an absolute path and --save."""
        base_file = f'/root/cfs-configs/{self.base_file_name}'
        full_args = self.common_args + ['--base-file', base_file, '--save']
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'],
                         self.get_bind_mount_str('/root/cfs-configs', INPUT_DATA_DIR))
        self.assertEqual(results['translated_args'],
                         ' '.join(self.common_args +
                                  ['--base-file', f'{INPUT_DATA_DIR}/{self.base_file_name}',
                                   '--save']))

    def test_base_file_current_dir_save_in_place(self):
        """Test with a --base-file specifying a file in the current directory and --save."""
        full_args = self.common_args + ['--base-file', self.base_file_name, '--save']
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'],
                         self.get_bind_mount_str('.', INPUT_DATA_DIR))
        self.assertEqual(results['translated_args'],
                         ' '.join(self.common_args +
                                  ['--base-file', f'{INPUT_DATA_DIR}/{self.base_file_name}',
                                   '--save']))

    def test_base_file_equals_save_in_place(self):
        """Test with --base-file=path option format."""
        full_args = self.common_args + [f'--base-file={self.base_file_name}', '--save']
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'],
                         self.get_bind_mount_str('.', INPUT_DATA_DIR))
        self.assertEqual(results['translated_args'],
                         ' '.join(self.common_args +
                                  [f'--base-file={INPUT_DATA_DIR}/{self.base_file_name}',
                                   '--save']))

    def test_base_file_save_to_file_same_dir(self):
        """Test with --base-file and --save-to-file pointing to files in the same directory."""
        common_dir = '/mnt/admin'
        base_file = f'{common_dir}/{self.base_file_name}'
        save_to_file = f'{common_dir}/{self.save_file_name}'
        full_args = self.common_args + ['--base-file', base_file,
                                        '--save-to-file', save_to_file]
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'],
                         ' '.join([self.get_bind_mount_str(common_dir, INPUT_DATA_DIR, readonly=True),
                                   self.get_bind_mount_str(common_dir, OUTPUT_DATA_DIR)]))
        self.assertEqual(results['translated_args'],
                         ' '.join(self.common_args +
                                  [f'--base-file', f'{INPUT_DATA_DIR}/{self.base_file_name}',
                                   '--save-to-file', f'{OUTPUT_DATA_DIR}/{self.save_file_name}']))

    def test_base_file_save_to_file_different_dirs(self):
        """Test with --base-file and --save-to-file pointing to files in different directories."""
        base_file = f'/root/{self.base_file_name}'
        save_to_file = f'/mnt/admin/{self.save_file_name}'
        full_args = self.common_args + ['--base-file', base_file,
                                        '--save-to-file', save_to_file]
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'],
                         ' '.join([self.get_bind_mount_str('/root', INPUT_DATA_DIR, readonly=True),
                                   self.get_bind_mount_str('/mnt/admin', OUTPUT_DATA_DIR)]))
        self.assertEqual(results['translated_args'],
                         ' '.join(self.common_args +
                                  [f'--base-file', f'{INPUT_DATA_DIR}/{self.base_file_name}',
                                   '--save-to-file', f'{OUTPUT_DATA_DIR}/{self.save_file_name}']))

    def test_base_file_save_suffix(self):
        """Test with --base-file and --save-suffix."""
        full_args = self.common_args + ['--base-file', self.base_file_name,
                                        '--save-suffix', '.new']
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'],
                         self.get_bind_mount_str('.', INPUT_DATA_DIR))
        self.assertEqual(results['translated_args'],
                         ' '.join(self.common_args +
                                  [f'--base-file', f'{INPUT_DATA_DIR}/{self.base_file_name}',
                                   '--save-suffix', '.new']))

    def test_base_config_save_to_file(self):
        """Test with --base-config=VALUE and --save-to-file."""
        full_args = self.common_args + ['--base-config=ncn-personalization',
                                        '--save-to-file', self.save_file_name]
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'],
                         self.get_bind_mount_str('.', OUTPUT_DATA_DIR))
        self.assertEqual(results['translated_args'],
                         ' '.join(self.common_args +
                                  ['--base-config=ncn-personalization',
                                   '--save-to-file', f'{OUTPUT_DATA_DIR}/{self.save_file_name}']))

    def test_base_config_save_to_cfs(self):
        """Test with --base-config and --save, which should require no mounts."""
        full_args = self.common_args + ['--base-config', 'mgmt-ncn-config', '--save']
        results = process_file_options(full_args)

        self.assertEqual(results['mount_opts'], '')
        self.assertEqual(results['translated_args'],
                         ' '.join(full_args))


if __name__ == '__main__':
    unittest.main()
