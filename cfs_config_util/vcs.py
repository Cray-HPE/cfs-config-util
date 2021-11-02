"""
Client for accessing VCS.

Copyright 2021 Hewlett Packard Enterprise Development LP
"""

import os
import subprocess
from urllib.parse import ParseResult, urlunparse

from cfs_config_util.cached_property import cached_property


class VCSError(Exception):
    """An error occurring during VCS access."""


class VCSRepo:
    """Main client object for accessing VCS."""
    _default_username = os.environ.get('VCS_USERNAME', 'crayvcs')

    def __init__(self, repo_path, username=None):
        """Constructor for VCSRepo.

        Args:
            repo_path (str): The path to the repo on the git server.
            username (str or None): if a str, then use this username to
                authenticate to the git server. If None, use the default
                username.
        """
        self.repo_path = repo_path

        if username is None:
            self.username = self._default_username
        else:
            self.username = username

    @property
    def remote_refs(self):
        """Get the remote refs for a remote repo.

        Args:
            vcs_username (str): username to authenticate to git server
            vcs_host (str): the hostname of the git server
            vcs_path (str): the path to the repository on the server

        Returns:
            dict: mapping of remote refs to their corresponding commit hashes

        Raises:
            VCSError: if there is an error when git accesses VCS to enumerate
                remote refs
        """

        user_netloc = f'{self.username}@{self.vcs_host}'
        url_components = ParseResult(scheme='https', netloc=user_netloc, path=self.repo_path,
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

    def get_commit_hash_for_version(self, product, version):
        """Get the commit hash for the configuration for some product version.

        Args:
            product (str): the name of the product
            version (str): the version string

        Returns:
            str or None: a commit hash corresponding to the given version,
                or None if the given version is not found.
        """
        target_ref = f'refs/heads/cray/{product}/{version}'
        return self.remote_refs.get(target_ref)

    @cached_property
    def vcs_host(self):
        """str: Hostname of the VCS server."""
        return 'api-gw-service-nmn.local'  # TODO: Update per CRAYSAT-898.

    @cached_property
    def clone_url(self):
        """str: a full, git-clone-able URL to the repository"""
        return urlunparse(('https', self.vcs_host, self.repo_path, '', '', ''))
