# MIT License
#
# (C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP
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
Client for accessing VCS.
"""

import os
import subprocess
from urllib.parse import ParseResult, urlparse, urlunparse


class VCSError(Exception):
    """An error occurring during VCS access."""


class VCSRepo:
    """Main client object for accessing VCS."""
    _default_username = os.environ.get('VCS_USERNAME', 'crayvcs')

    def __init__(self, clone_url, username=None):
        """Constructor for VCSRepo.

        Args:
            clone_url (str): The clone URL for the VCS repo.
            username (str or None): if a str, then use this username to
                authenticate to the git server. If None, use the default
                username.
        """
        self.clone_url = clone_url

        if username is None:
            self.username = self._default_username
        else:
            self.username = username

    @property
    def remote_refs(self):
        """Get the remote refs for a remote repo.

        Returns:
            dict: mapping of remote refs to their corresponding commit hashes

        Raises:
            VCSError: if there is an error when git accesses VCS to enumerate
                remote refs
        """
        parsed_clone_url = urlparse(self.clone_url)
        user_netloc = f'{self.username}@{parsed_clone_url.netloc}'
        url_components = ParseResult(scheme='https', netloc=user_netloc, path=parsed_clone_url.path,
                                     params='', query='', fragment='')
        vcs_full_url = urlunparse(url_components)

        # Get the password directly from k8s to avoid leaking it via the /proc
        # filesystem.
        env = dict(os.environ)
        env.update(GIT_ASKPASS='vcs-creds-helper')
        try:
            proc = subprocess.run(['git', 'ls-remote', vcs_full_url],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=env, check=True)
        except subprocess.CalledProcessError as err:
            raise VCSError(f"Error accessing VCS: {err}") from err

        # Each line in the output from `git ls-remote` has the form
        # "<commit_hash>\t<ref_name>", and we want the returned dictionary to map
        # the other way, i.e. from ref names to commit hashes. Thus when we split
        # each line on '\t', we should reverse the order of the resulting pair
        # before inserting it into the dictionary (hence the `reversed` in the
        # following comprehension.)
        return dict(
            tuple(reversed(line.split('\t')))
            for line in proc.stdout.decode('utf-8').split('\n')
            if line
        )

    def get_commit_hash_for_branch(self, branch):
        """Get the commit hash for a branch of this VCSRepo

        Args:
            branch (str): the branch to resolve to a commit hash

        Returns:
            str or None: a commit hash corresponding to the given version,
                or None if the given version is not found.

        Raises:
            VCSError: if there is an error converting the branch to a commit hash
        """
        return self.remote_refs.get(f'refs/heads/{branch}')
