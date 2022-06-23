"""
A small program to retrieve the VCS password from k8s secrets.

This program is intended to be called using `GIT_ASKPASS` and prints the
password to standard output. Use with care.

Copyright 2021 Hewlett Packard Enterprise Development LP
"""

import base64
import sys

from cfs_config_util.apiclient import load_kube_api


def main():
    """Get the VCS password from the k8s store.

    Returns:
        str: the VCS password
    """
    k8s = load_kube_api()
    secret = k8s.read_namespaced_secret('vcs-user-credentials', 'services').data.get('vcs_password')
    if secret is None:
        sys.exit('Could not retrieve password from k8s secrets')
    print(base64.b64decode(secret.encode('utf-8')).decode('utf-8').strip())
