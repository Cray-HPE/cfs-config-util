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
"""A small program to retrieve the VCS password from k8s secrets.

This program is intended to be called using `GIT_ASKPASS` and prints the
password to standard output. Use with care.
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
