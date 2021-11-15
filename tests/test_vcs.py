"""
Tests for VCS utility classes and functions.

Copyright (C) 2021 Hewlett Packard Enterprise Development LP. All Rights Reserved.
"""

from textwrap import dedent
import subprocess
import unittest
from unittest.mock import patch, PropertyMock

from cfs_config_util.vcs import VCSError, VCSRepo


class TestVCSRepo(unittest.TestCase):
    """Tests for the VCSRepo class."""
    def setUp(self):
        self.mock_subprocess_run = patch('cfs_config_util.vcs.subprocess.run').start()

    def tearDown(self):
        patch.stopall()

    def test_default_username(self):
        """Test that the VCSRepo constructor sets the default username when None supplied"""
        repo = VCSRepo('foo/bar.git')
        self.assertEqual(repo.username, VCSRepo._default_username)

    def test_getting_remote_refs(self):
        """Test getting remote refs from VCS"""
        self.mock_subprocess_run.return_value.stdout = dedent("""\
        e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e	HEAD
        7448d8798a4380162d4b56f9b452e2f6f9e24e7a	foo
        a3db5c13ff90a36963278c6a39e4ee3c22e2a436	bar
        """).encode('utf-8')

        repo = VCSRepo('foo/bar.git')
        self.assertEqual(repo.remote_refs, {
            'HEAD': 'e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e',
            'foo': '7448d8798a4380162d4b56f9b452e2f6f9e24e7a',
            'bar': 'a3db5c13ff90a36963278c6a39e4ee3c22e2a436',
        })

    def test_remote_refs_raises_vcs_error(self):
        """Test that getting remote refs throws an error when git issues occur"""
        self.mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, b'git ls-remote')
        repo = VCSRepo('foo/bar.git')
        with self.assertRaises(VCSError):
            _ = repo.remote_refs

    def test_getting_commit_hashes_for_versions(self):
        """Test getting a commit hash for the current version"""
        with patch('cfs_config_util.vcs.VCSRepo.remote_refs',
                   new_callable=PropertyMock) as mock_remote_refs:
            version = '2.0.0'
            commit_hash = '6e42d6e57855cfe022c5481efa7c971114ee1688'
            mock_remote_refs.return_value = {
                'refs/heads/cray/sat/2.0.0': commit_hash,
                'refs/heads/cray/sat/2.1.0': '13a290994ff4102d5380e140bc1c0bd6fb112900',
            }
            retrieved_hash = VCSRepo('foo/bar.git').get_commit_hash_for_version('sat', '2.0.0')
            self.assertEqual(retrieved_hash, commit_hash)

    def test_getting_clone_url(self):
        """Test retrieving the clone URL for the repo"""
        with patch('cfs_config_util.vcs.VCSRepo.vcs_host',
                   new_callable=PropertyMock) as mock_vcs_host:
            host = 'vcs.local'
            path = 'foo/bar.git'
            mock_vcs_host.return_value = host
            repo = VCSRepo(path)
            self.assertEqual(f'https://{host}/{path}', repo.clone_url)