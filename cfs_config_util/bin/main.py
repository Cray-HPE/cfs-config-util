"""
Main entrypoint to CFS update utility

Copyright 2021-2022 Hewlett Packard Enterprise Development LP
"""

import argparse
import json
import logging

from cfs_config_util.apiclient import APIError, HSMClient
from cfs_config_util.cfs import CFSClient
from cfs_config_util.parser import check_args, create_parser, BASE_QUERY_OPTION
from cfs_config_util.session import AdminSession
from cfs_config_util.cfs import CFSConfiguration, CFSConfigurationError, CFSConfigurationLayer

LOGGER = logging.getLogger(__name__)


def configure_logging():
    """Configure logging for the cfs-config-util executable.

    This sets up the root logger with the default format, INFO log level, and
    stderr log handler.

    Returns:
        None.
    """
    console_log_format = '%(levelname)s: %(message)s'
    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(console_log_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)


def get_cfs_configurations(args, cfs_client, hsm_client):
    """Get the CFSConfigurations from CFS or from a file.

    Args:
        args (argparse.Namespace): the parsed command-line args
        cfs_client (cfs_config_util.cfs.CFSClient): the CFS API client
        hsm_client (cfs_config_util.apiclient.HSMClient): the HSM API client

    Returns:
        list of cfs_config_util.cfs.CFSConfiguration: the CFS configurations
            from CFS or loaded from a file. If a name of a CFS config or a file
            name is given, the list will have only one element.

    Raises:
        CFSConfigurationError: if unable get the CFS configuration from the CFS
            API or unable to load it from a file
    """
    if args.base_config is not None:
        # Get the CFSConfiguration from the CFS API
        try:
            return [cfs_client.get_configuration(args.base_config)]
        except APIError as err:
            raise CFSConfigurationError(f'Could not retrieve configuration '
                                        f'"{args.base_config}" from CFS: {err}')

    elif args.base_query is not None:
        # Protect against an empty query returning all components
        if not args.base_query:
            raise CFSConfigurationError(f'Query params specified by {BASE_QUERY_OPTION} '
                                        f'must be non-empty.')
        try:
            query_params = {param: value for param, value in
                            [query.split('=', maxsplit=1) for query in args.base_query.split(',')]}
        except ValueError:
            raise CFSConfigurationError(
                f'Invalid query "{args.base_query}". Query string must consist '
                f'of one or more comma-separated key=value pairs.'
            )

        try:
            return cfs_client.get_configurations_for_components(hsm_client, **query_params)
        except APIError as err:
            raise CFSConfigurationError(
                f'Could not retrieve CFS configurations for HSM components '
                f'matching the query "{args.base_query}": {err}'
            )

    else:
        # args.base_file must have been specified, so load from a file
        try:
            with open(args.base_file, 'r') as f:
                file_data = json.load(f)
        except OSError as err:
            raise CFSConfigurationError(f'Failed to open file {args.base_file}: {err}')
        except json.decoder.JSONDecodeError as err:
            raise CFSConfigurationError(f'Failed to parse JSON in file {args.base_file}: {err}')

        return [CFSConfiguration(cfs_client, file_data)]


def construct_layer(args):
    """Construct a CFSConfigurationLayer which should be added or removed from a CFSConfiguration.

    Args:
        args (argparse.Namespace): the parsed command-line args

    Returns:
        CFSConfigurationLayer: the layer that should be added or removed

    Raises:
        CFSConfigurationError: if unable to construct the requested layer
    """
    # These kwargs are common between both layers defined by clone URL and layers
    # defined by product.
    common_args = {
        'name': args.layer_name,
        'playbook': args.playbook,
        'commit': args.git_commit,
        'branch': args.git_branch
    }
    if args.product:
        if ':' in args.product:
            product_name, product_version = args.product.split(':', maxsplit=1)
        else:
            product_name = args.product
            product_version = None
        return CFSConfigurationLayer.from_product_catalog(
            product_name, product_version=product_version, **common_args)
    else:
        return CFSConfigurationLayer.from_clone_url(args.clone_url, **common_args)


def save_cfs_configuration(args, cfs_config):
    """Save the CFSConfiguration to a file or to CFS per the command-line args.

    Args:
        args (argparse.Namespace): the parsed command-line args
        cfs_config (cfs_config_util.cfs.CFSConfiguration): the modified
            CFS configuration to save

    Returns:
        None

    Raises:
        CFSConfigurationError: if unable to save the CFS configuration to CFS
            or to a file.
    """
    if args.save:
        if args.base_config or args.base_query:
            # Overwrite the CFS configuration in CFS
            cfs_config.save_to_cfs()
        else:
            # args.base_file; overwrite the file in place
            cfs_config.save_to_file(args.base_file)

    elif args.save_suffix:
        if args.base_config or args.base_query:
            cfs_config.save_to_cfs(f'{cfs_config.name}{args.save_suffix}')
        else:
            cfs_config.save_to_file(f'{args.base_file}{args.save_suffix}')

    elif args.save_to_cfs:
        cfs_config.save_to_cfs(args.save_to_cfs)

    elif args.save_to_file:
        cfs_config.save_to_file(args.save_to_file)


def main():
    """Modify a CFS configuration and save it as specified by the command-line args.

    Returns:
        None

    Raises:
        SystemExit: if there is a failure to get the base config, modify it, or save it
    """
    configure_logging()

    parser = create_parser()
    args = parser.parse_args()
    try:
        check_args(args)
    except ValueError as err:
        LOGGER.error(str(err))
        raise SystemExit(1)

    session = AdminSession.get_session()
    hsm_client = HSMClient(session)
    cfs_client = CFSClient(session)
    try:
        base_configs = get_cfs_configurations(args, cfs_client, hsm_client)
        layer = construct_layer(args)

        if args.resolve_branches:
            layer.resolve_branch_to_commit_hash()

    except CFSConfigurationError as err:
        LOGGER.error(str(err))
        raise SystemExit(1)

    succeeded, skipped, failed = [], [], []
    for base_config in base_configs:
        base_config.ensure_layer(layer, args.state)

        if not base_config.changed:
            skipped.append(base_config)
            continue

        try:
            save_cfs_configuration(args, base_config)
            succeeded.append(base_config)
        except CFSConfigurationError as err:
            LOGGER.error(str(err))
            failed.append(base_config)

    if skipped:
        LOGGER.info(f'Skipped saving {len(skipped)} unchanged CFS configurations.')

    if succeeded:
        LOGGER.info(f'Successfully saved {len(succeeded)} changed CFS configurations.')

    if failed:
        LOGGER.error(f'Failed to save {len(failed)} CFS configurations.')
        raise SystemExit(1)
