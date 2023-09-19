#
# MIT License
#
# (C) Copyright 2021-2023 Hewlett Packard Enterprise Development LP
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
from collections import defaultdict

from csm_api_client.service.cfs import LayerState

PRODUCT_OPTION = '--product'
CLONE_URL_OPTION = '--clone-url'
GIT_BRANCH_OPTION = '--git-branch'
GIT_COMMIT_OPTION = '--git-commit'
STATE_OPTION = '--state'

BASE_CONFIG_OPTION = '--base-config'
BASE_FILE_OPTION = '--base-file'
BASE_QUERY_OPTION = '--base-query'

SAVE_OPTION = '--save'
SAVE_TO_FILE_OPTION = '--save-to-file'
SAVE_TO_CFS_OPTION = '--save-to-cfs'
SAVE_SUFFIX_OPTION = '--save-suffix'

ASSIGN_TO_XNAMES_OPTION = '--assign-to-xnames'
ASSIGN_TO_QUERY_OPTION = '--assign-to-query'

CLEAR_STATE_OPTION = '--clear-state'
CLEAR_ERROR_OPTION = '--clear-error'
ENABLE_OPTION = '--enable'
DISABLE_OPTION = '--disable'

DESIRED_CONFIG_OPTION = '--desired-config'

CANONICAL_UPDATE_CONFIGS_ACTION = 'update-configs'
CANONICAL_UPDATE_COMPONENTS_ACTION = 'update-components'


def convert_comma_separated_list(comma_separated_str):
    """Convert a comma-separated list into a list.

    Args:
        comma_separated_str (str): the comma-separated list string to convert

    Returns:
        list: the converted list
    """
    return comma_separated_str.split(',')


def convert_query_to_dict(query_str):
    """Convert a comma-separated list of query parameters to a dictionary.

    This splits a list of comma-separated items of the form "param=value" and
    adds them to a dictionary mapping from param to the list of values for that
    param. Multiple instances of a single param are added to a list of values.

    For example "role=management,subrole=master,subrole=storage" becomes:

    {
        "role": ["management"]
        "subrole": ["master", "storage"]
    }

    Args:
        query_str (str): the comma-separated parameters

    Returns:
        dict: a dictionary mapping from parameter names to their string value
            or values.
    """
    params = defaultdict(list)
    for query in query_str.split(','):
        try:
            param, value = query.split('=', maxsplit=1)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f'Invalid query string "{query_str}". Query string must consist '
                f'of one or more comma-separated key=value pairs.'
            )
        params[param].append(value)

    return dict(params)


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
        '--playbook', action='append', dest='playbooks', metavar='playbook',
        help='The name of the playbook for the layer being targeted. If not '
             'specified, then no playbook will be specified in the layer, '
             'which means CFS will use its internal default. If specified '
             'multiple times, then a separate layer will be targeted for each '
             'given playbook.'
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
    base_mutex_group = base_group.add_mutually_exclusive_group()
    base_mutex_group.add_argument(
        BASE_CONFIG_OPTION,
        help='The name of the CFS configuration in CFS to use as a base.'
    )
    base_mutex_group.add_argument(
        BASE_FILE_OPTION,
        help='The path to a file containing a CFS configuration payload.'
    )
    base_mutex_group.add_argument(
        BASE_QUERY_OPTION, type=convert_query_to_dict,
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
        SAVE_OPTION, action='store_true',
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
        SAVE_SUFFIX_OPTION,
        help=f'If specified, save the configuration with a new name created '
             f'by appending this suffix. If {BASE_CONFIG_OPTION} is specified, '
             f'a new CFS configuration named with this suffix is created. If '
             f'{BASE_FILE_OPTION} is specified, a new file with this suffix '
             f'will be created. If {BASE_QUERY_OPTION} is specified, each '
             f'discovered will be saved to a new CFS configuration with this '
             f'suffix.'
    )
    save_group.add_argument(
        '--create-backups', action='store_true',
        help='If specified, save a backup of any configuration which is '
             'overwritten.'
    )


def add_assign_options(parser):
    """Add options which control how to assign the modified CFS configuration.

    Args:
        parser (argparse.ArgumentParser): the parser to which args are added
    """
    assign_group = parser.add_argument_group(
        title='Assign Options',
        description='Options that control how the modified CFS configuration '
                    'is assigned to CFS components.'
    )

    assign_disclaimer = ('This option can only be used when a single CFS '
                         'configuration is being created or modified.')

    assign_group.add_argument(
        ASSIGN_TO_XNAMES_OPTION, metavar='XNAME', type=convert_comma_separated_list,
        help=f'A comma-separated list of xnames of CFS components to which the '
             f'configuration should be assigned. {assign_disclaimer}'
    )
    assign_group.add_argument(
        ASSIGN_TO_QUERY_OPTION, metavar='HSM_QUERY', type=convert_query_to_dict,
        help=f'A comma-separated list of key-value pairs to use to query '
             f'for HSM components. Matching CFS components will then have '
             f'the configuration assigned. {assign_disclaimer}'
    )


def add_apply_options(parser):
    """Add options which control how to apply a CFS configuration to components.

    Args:
        parser (argparse.ArgumentParser): the parser to which args are added

    Returns:
        argparse._ArgumentGroup: the argument group added to parser
    """
    apply_group = parser.add_argument_group(
        title='Apply Options',
        description='Options that control how the modified CFS configuration '
                    'is applied to CFS components.'
    )

    apply_group.add_argument(
        CLEAR_STATE_OPTION, action='store_true',
        help='If specified, clear the state of the CFS components when the '
             'configuration is assigned. This will force CFS to re-apply all '
             'layers of the CFS configuration.'
    )
    apply_group.add_argument(
        CLEAR_ERROR_OPTION, action='store_true',
        help='If specified, clear the error count of the CFS components when '
             'the configuration is assigned. This will allow CFS to attempt to '
             're-apply a CFS configuration if the error count has been exceeded.'
    )

    enable_group = apply_group.add_mutually_exclusive_group()
    enable_group.add_argument(
        ENABLE_OPTION, action='store_true', dest='enabled', default=None,
        help='If specified, ensure all CFS components affected are enabled.'
    )
    enable_group.add_argument(
        DISABLE_OPTION, action='store_false', dest='enabled', default=None,
        help='If specified, ensure all CFS components affected are disabled.'
    )

    apply_group.add_argument(
        '--no-wait', action='store_false', dest='wait',
        help='If specified, do not wait for the affected CFS components to '
             'finish their configuration.'
    )

    return apply_group


def base_given(args):
    """Check if a base was specified.

    Returns:
        bool: True if any of --base-config, --base-file, or --base-query was
        specified, and False otherwise.
    """
    return any([args.base_config, args.base_file, args.base_query])


def saves_to_cfs(args):
    """Check if the resulting configuration will be saved to CFS.

    Returns:
        bool: True if the CFS configuration will be saved to CFS, False otherwise
    """
    # If explicitly saved to CFS or the base is in CFS and not being saved to a
    # file, then the modified CFS configuration will be saved to CFS.
    return bool(args.save_to_cfs or
                ((args.base_config or args.base_query) and not args.save_to_file))


def assign_requested(args):
    """Check if assignment of a configuration to components was requested.

    Returns:
        bool: True if the admin requested that the CFS configuration be assigned
            to CFS components.
    """
    return any([args.assign_to_xnames, args.assign_to_query])


def apply_options_provided(args):
    """Check if any options affecting how configurations are applied were specified.

    Returns:
        bool: True if the admin specified options affecting the application of
            the configuration, False otherwise.
    """
    return any([args.clear_state, args.clear_error, args.enabled is not None])


def check_update_configs_args(args):
    """Check that the specified args to the update-configs action are compatible.

    Args:
        args (argparse.Namespace): the parsed command-line args

    Raises:
        ValueError: if any incompatible args are specified.
    """
    if not base_given(args) and (args.save or args.save_suffix):
        raise ValueError(f'If none of {BASE_CONFIG_OPTION}, {BASE_FILE_OPTION}, '
                         f'or {BASE_QUERY_OPTION} is used, then neither {SAVE_OPTION} '
                         f'nor {SAVE_SUFFIX_OPTION} may be used.')

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

    if assign_requested(args) and not saves_to_cfs(args):
        raise ValueError(
            f'The {ASSIGN_TO_XNAMES_OPTION} or {ASSIGN_TO_QUERY_OPTION} options '
            f'require the resulting CFS configuration to be saved to CFS.'
        )

    if assign_requested(args) and args.base_query is not None:
        raise ValueError(
            f'{BASE_QUERY_OPTION} is not compatible with {ASSIGN_TO_QUERY_OPTION} '
            f'or {ASSIGN_TO_XNAMES_OPTION}.'
        )

    if apply_options_provided(args) and not saves_to_cfs(args):
        raise ValueError(
            f'The options {CLEAR_STATE_OPTION}, {CLEAR_ERROR_OPTION}, '
            f'{ENABLE_OPTION}, or {DISABLE_OPTION} require the resulting '
            f'CFS configuration be saved to CFS.'
        )


def check_update_components_args(args):
    """Check that the specified args to the update-components action are compatible.

    Args:
        args (argparse.Namespace): the parsed command-line args

    Raises:
        ValueError: if any incompatible args are specified.
    """
    if not any([args.desired_config, args.clear_state, args.clear_error, args.enabled is not None]):
        raise ValueError(
            f'At least one of the options {DESIRED_CONFIG_OPTION}, '
            f'{CLEAR_STATE_OPTION}, {CLEAR_ERROR_OPTION}, {ENABLE_OPTION}, '
            f'or {DISABLE_OPTION} must be specified.'
        )


def check_args(args):
    """Check that the specified args are compatible.

    Args:
        args (argparse.Namespace): the parsed command-line args

    Raises:
        ValueError: if any incompatible args are specified.
    """
    if args.canonical_action == CANONICAL_UPDATE_CONFIGS_ACTION:
        check_update_configs_args(args)
    elif args.canonical_action == CANONICAL_UPDATE_COMPONENTS_ACTION:
        check_update_components_args(args)


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

    # Add subset of the options added by add_layer_content_options
    git_group = parser.add_argument_group(
        title='Git Options',
        description='Options that control the git ref used in the layer.'
    )
    add_git_options(git_group)
    add_base_options(parser)
    add_save_options(parser)
    add_assign_options(parser)

    return parser


def add_update_configs_subparser(subparsers):
    """Add the update-configs subparser to the parent parser.

    The update-configs action is used to modify create a new CFS configuration
    or modify an existing one. This action used to be the default behavior when
    no action was given.

    Args:
        subparsers (argparse._SubParsersAction): the object to which subparsers
            can be added with add_subparser

    Returns: None
    """
    subparser = subparsers.add_parser(
        CANONICAL_UPDATE_CONFIGS_ACTION, help='Update CFS configurations.',
        aliases=['update-config', 'update-configurations', 'update-configuration'],
        description='Update one or more CFS configurations and optionally '
                    'assign them to components in CFS.'
    )
    subparser.set_defaults(canonical_action=CANONICAL_UPDATE_CONFIGS_ACTION)

    add_layer_content_options(subparser)
    add_base_options(subparser)
    add_save_options(subparser)
    add_assign_options(subparser)
    add_apply_options(subparser)


def add_update_components_subparser(subparsers):
    """Add the update-components subparser to the parent parser.

    The update-components action is used to update the attributes of CFS components,
    including their desiredConfig, enabled, errorCount, and state attributes. It
    will also wait for the components to reach a configured state if a change which
    would trigger CFS Batcher is made.

    Args:
        subparsers (argparse._SubParsersAction): the object to which subparsers
            can be added with add_subparser

    Returns: None
    """
    subparser = subparsers.add_parser(
        CANONICAL_UPDATE_COMPONENTS_ACTION, help='Update CFS components.',
        aliases=['update-component'],
        description='Update CFS components and optionally wait for them to become '
                    'configured by CFS Batcher.'
    )
    subparser.set_defaults(canonical_action=CANONICAL_UPDATE_COMPONENTS_ACTION)

    subparser.add_argument(
        '--xnames', metavar='XNAME', type=convert_comma_separated_list,
        help=f'A comma-separated list of xnames of CFS components which should '
             f'be updated.'
    )
    subparser.add_argument(
        '--query', metavar='HSM_QUERY', type=convert_query_to_dict,
        help=f'A comma-separated list of key-value pairs to use to query '
             f'for HSM components. Matching CFS components will then have '
             f'the specified configuration assigned.'
    )

    apply_group = add_apply_options(subparser)
    apply_group.add_argument(
        DESIRED_CONFIG_OPTION,
        help=f'The CFS configuration which should be set as the desiredConfig '
             f'for the given components. If not specified, the desiredConfig is '
             f'not set on the components.'
    )


def create_parser():
    """Create the parser for the cfs-config-util entry point.

    Returns:
        argparse.ArgumentParser: the parser
    """
    parser = argparse.ArgumentParser(allow_abbrev=False)

    subparsers = parser.add_subparsers(metavar='action', dest='action')
    add_update_configs_subparser(subparsers)
    add_update_components_subparser(subparsers)

    return parser
