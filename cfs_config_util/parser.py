#
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
Parser definition for cfs-config-util entry point.
"""

import argparse

from cfs_config_util.cfs import LayerState

PRODUCT_OPTION = '--product'
CLONE_URL_OPTION = '--clone-url'
GIT_BRANCH_OPTION = '--git-branch'
GIT_COMMIT_OPTION = '--git-commit'
STATE_OPTION = '--state'

BASE_CONFIG_OPTION = '--base-config'
BASE_FILE_OPTION = '--base-file'
BASE_QUERY_OPTION = '--base-query'

SAVE_TO_FILE_OPTION = '--save-to-file'
SAVE_TO_CFS_OPTION = '--save-to-cfs'


def add_git_options(group):
    """Add options which control which git ref is used in a layer.

    Args:
        group (argparse._ArgumentGroup): the parser group to which args are added

    Returns: None
    """
    common_git_help = (
        f'If {CLONE_URL_OPTION} is specified, either {GIT_BRANCH_OPTION} or '
        f'{GIT_COMMIT_OPTION} is required. Otherwise, if {PRODUCT_OPTION} is '
        f'specified and neither {GIT_BRANCH_OPTION} nor {GIT_COMMIT_OPTION} is '
        f'specified, the git commit hash from the "commit" key '
        f'in the product catalog data will be used.'
    )
    git_ref_mutex_group = group.add_mutually_exclusive_group()
    git_ref_mutex_group.add_argument(
        GIT_BRANCH_OPTION,
        help=f'The git branch to resolve to a commit hash and specify in the '
             f'configuration layer in CFS. {common_git_help}'
    )
    git_ref_mutex_group.add_argument(
        GIT_COMMIT_OPTION,
        help=f'The git commit hash to specify in the configuration layer in CFS. '
             f'{common_git_help}'
    )

    group.add_argument(
        '--no-resolve-branches', action='store_false', dest='resolve_branches',
        help='Do not resolve branch names to corresponding commit hashes before '
             'creating creating the CFS configuration layer.'
    )


def add_layer_content_options(parser):
    """Add options which control the content of the layer to be added or removed.

    Args:
        parser (argparse.ArgumentParser): the parser to which args are added

    Returns: None
    """
    repo_group = parser.add_argument_group(
        title='VCS Repo Options',
        description='Options that control the content of the layer to be added '
                    'or removed.'
    )
    repo_mutex_group = repo_group.add_mutually_exclusive_group(required=True)
    repo_mutex_group.add_argument(
        PRODUCT_OPTION,
        help='The name and version of the product providing the configuration '
             'management repo in VCS. Specified in the format PRODUCT_NAME[:PRODUCT_VERSION]. '
             'If the version is omitted, the latest version of that product is assumed.'
    )
    repo_mutex_group.add_argument(
        CLONE_URL_OPTION,
        help='The git repository clone URL to use in the configuration layer '
             'in CFS. If not specified, but a product name is specified, the '
             'repository URL will be determined from the product catalog.'
    )

    repo_group.add_argument(
        '--layer-name',
        help=f'The name of the configuration layer to create when {STATE_OPTION} '
             f'{LayerState.PRESENT} is specified. Has no effect if used with '
             f'{STATE_OPTION} {LayerState.ABSENT}. If not specified, the layer '
             f'name is constructed from the other options.'
    )

    repo_group.add_argument(
        '--playbook',
        help='The name of the playbook for the layer being targeted. If not '
             'specified, then no playbook will be specified in the layer, '
             'which means CFS will use its internal default.'
    )

    repo_group.add_argument(
        STATE_OPTION, default=LayerState.PRESENT, choices=LayerState,
        type=LayerState,
        help='Whether to ensure the layer for this version of this product '
             'is present or absent. Defaults to ensuring the layer is present.'
    )

    add_git_options(repo_group)


def add_base_options(parser):
    """Add options which control the CFS configuration to use as a base.

    Args:
        parser (argparse.ArgumentParser): the parser to which args are added
    """
    base_group = parser.add_argument_group(
        title='Base Configuration Options',
        description='Options that control the CFS configuration to use as '
                    'a base for the modifications performed by this tool.'
    )
    base_mutex_group = base_group.add_mutually_exclusive_group(required=True)
    base_mutex_group.add_argument(
        BASE_CONFIG_OPTION,
        help='The name of the CFS configuration in CFS to use as a base. If no '
             'such CFS configuration exists, start from an empty set of layers.'
    )
    base_mutex_group.add_argument(
        BASE_FILE_OPTION,
        help='The path to a file containing a CFS configuration payload. '
             'If no such file exists, start from an empty set of layers.'
    )
    base_mutex_group.add_argument(
        BASE_QUERY_OPTION,
        help=f'A comma-separated list of key-value pairs to use to query '
             f'for HSM components, which will then be queried in CFS to '
             f'find a base configuration. Not compatible with {SAVE_TO_CFS_OPTION} '
             f'or {SAVE_TO_FILE_OPTION}.'
    )


def add_save_options(parser):
    """Add options which control how to save the modified CFS configuration.

    Args:
        parser (argparse.ArgumentParser): the parser to which args are added
    """
    save_group = parser.add_argument_group(
        title='Save Options',
        description='Options that control how the modified CFS configuration '
                    'content is saved.'
    )
    save_mutex_group = save_group.add_mutually_exclusive_group(required=True)
    save_mutex_group.add_argument(
        '--save', action='store_true',
        help=f'If specified, save the modified configuration in place. If '
             f'{BASE_CONFIG_OPTION} is specified, the CFS configuration with '
             f'that name will be updated. If {BASE_FILE_OPTION} is specified, '
             f'the file contents will be updated. If {BASE_QUERY_OPTION} is '
             f'specified, each discovered CFS configuration will be updated.'
    )
    save_mutex_group.add_argument(
        SAVE_TO_CFS_OPTION, metavar='NEW_CFS_CONFIG_NAME',
        help='If specified, save the modified configuration as a configuration '
             f'with the given name in CFS. Not compatible with {BASE_QUERY_OPTION}.'
    )
    save_mutex_group.add_argument(
        SAVE_TO_FILE_OPTION, metavar='NEW_FILE_NAME',
        help='If specified, save the modified configuration layers to the given '
             f'file name. Not compatible with {BASE_QUERY_OPTION}.'
    )
    save_mutex_group.add_argument(
        '--save-suffix',
        help=f'If specified, save the configuration with a new name created '
             f'by appending this suffix. If {BASE_CONFIG_OPTION} is specified, '
             f'a new CFS configuration named with this suffix is created. If '
             f'{BASE_FILE_OPTION} is specified, a new file with this suffix '
             f'will be created. If {BASE_QUERY_OPTION} is specified, each '
             f'discovered will be saved to a new CFS configuration with this '
             f'suffix.'
    )


def check_args(args):
    """Check that the specified args are compatible.

    Args:
        args (argparse.Namespace): the parsed command-line args

    Raises:
        ValueError: if any incompatible args are specified.
    """
    if args.base_query is not None and any([args.save_to_cfs, args.save_to_file]):
        raise ValueError(
            f'{BASE_QUERY_OPTION} is not compatible with {SAVE_TO_CFS_OPTION} '
            f'or {SAVE_TO_FILE_OPTION}.'
        )

    if args.clone_url and not any([args.git_branch, args.git_commit]):
        raise ValueError(
            f'If {CLONE_URL_OPTION} is specified, then either {GIT_BRANCH_OPTION} '
            f'or {GIT_COMMIT_OPTION} must be specified.'
        )


def create_passthrough_parser():
    """Create a parser for options that can be passed through product install scripts.

    The cfs-config-util container image is run under `podman` by scripts
    included in each product's install media. Some of the cfs-config-util
    options are known by the product installer (e.g. the name and version of the
    product, the playbook name), while other options may need to be passed
    through to allow the admin flexibility in how they perform their install.

    This creates a parser that contains just those passthrough options. This
    parser can be used to output the usage information for just those options,
    which can then be displayed by the installer script.

    Returns:
        argparse.ArgumentParser: the parser containing just the passthrough args
    """
    parser = argparse.ArgumentParser(add_help=False, usage=argparse.SUPPRESS, allow_abbrev=False)

    git_group = parser.add_argument_group(
        title='Git Options',
        description='Options that control the git ref used in the layer.'
    )
    add_git_options(git_group)
    add_base_options(parser)
    add_save_options(parser)

    return parser


def create_parser():
    """Create the parser for the cfs-config-util entry point.

    Returns:
        argparse.ArgumentParser: the parser
    """
    parser = argparse.ArgumentParser(allow_abbrev=False)

    add_layer_content_options(parser)
    add_base_options(parser)
    add_save_options(parser)

    return parser
