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
Entry point used by product installers to determine mounts needed to run in container.

This entry point parses the options provided to cfs-config-util, identifies
which files are being modified, and then outputs information about the mount
options which should be added to a podman call to ensure that the files are
accessible in the container environment and the translated options with any
file paths replaced with paths inside the container environment.

This information is dumped in JSON format so it can easily be accessed in a shell
script using the `jq` utility.
"""
from dataclasses import dataclass
import json
import os
import sys

from cfs_config_util.parser import create_parser, BASE_FILE_OPTION, SAVE_TO_FILE_OPTION

DATA_DIR = '/data/'
INPUT_DATA_DIR = os.path.join(DATA_DIR, 'input')
OUTPUT_DATA_DIR = os.path.join(DATA_DIR, 'output')


@dataclass
class BindMount:
    """Class to describe a bind mount needed by `podman run` invocation."""
    source: str
    target: str
    readonly: bool = False

    @property
    def mount_option_str(self):
        """str: the mount option string to pass to `podman run`"""
        return (f'--mount type=bind,src={self.source},target={self.target}'
                f'{",ro=true" if self.readonly else ""}')


def _replace_option_value(args, option_to_modify, new_value):
    """Replace option values in the given list of arguments.

    It would be better to do this in argparse to ensure arguments are parsed
    correctly and consistently with how the actual program parses them, but this
    works in most situations.

    Note that this will not work correctly to modify any arguments which use
    action='append' in argparse since all instances of that option will have
    their values replaced with the same value, which will result in the parsed
    option value having duplicates.

    Args:
        args (list of str): the arguments passed to the program
        option_to_modify (str): the option whose value should be modified. This
            assumes the option has only a long form.
        new_value (str): the new value to set for the option

    Returns:
        list of str: the given arguments modified to replace the value of the
            option if it was specified.
    """
    new_args = []
    replace_next = False
    for arg in args:
        if replace_next:
            # Identified as the option value to be replaced on previous iteration
            new_args.append(new_value)
            replace_next = False
        # Support replacing option values specified as '--option=value'
        elif arg.startswith('--') and '=' in arg:
            option = arg.split('=')[0]
            if option == option_to_modify:
                new_args.append(f'{option}={new_value}')
            else:
                new_args.append(arg)
        else:
            if arg == option_to_modify:
                # The next argument in args is the option value
                replace_next = True
            # This was either the matching option string or some other argument
            new_args.append(arg)

    return new_args


def process_file_options(provided_args):
    """Process the file options in the provided arguments.

    Args:
        provided_args (list): the list of arguments to be processed

    Returns:
        A dictionary containing the following keys:
            mount_opts (str): the mount options to pass to the container runtime
                to ensure the appropriate files are available in the container
            translated_args (str): the original arguments with any file paths
                translated to their new paths where they will be mounted inside
                the container.
    """
    translated_args = provided_args
    parser = create_parser()
    parsed_args = parser.parse_args(provided_args)

    bind_mounts = []

    if parsed_args.base_file:
        orig_input_dir = os.path.dirname(parsed_args.base_file) or '.'
        new_base_file = os.path.join(INPUT_DATA_DIR, os.path.basename(parsed_args.base_file))
        translated_args = _replace_option_value(translated_args, BASE_FILE_OPTION, new_base_file)
        # If not saving to this same directory, then mount read-only
        read_only_input_dir = not (parsed_args.save or parsed_args.save_suffix)
        bind_mounts.append(BindMount(orig_input_dir, INPUT_DATA_DIR, read_only_input_dir))

    if parsed_args.save_to_file:
        orig_output_dir = os.path.dirname(parsed_args.save_to_file) or '.'
        new_save_file = os.path.join(OUTPUT_DATA_DIR, os.path.basename(parsed_args.save_to_file))
        translated_args = _replace_option_value(translated_args, SAVE_TO_FILE_OPTION, new_save_file)

        # Note: from within the container, it is impossible to determine if the input
        # and output dir are the same (or if one is a subdirectory of the other), so
        # this might mount the same directory at two locations, but if it does, only
        # this mount will be read-write because args.save, args.save_suffix, and
        # args.save_to_file are mutually exclusive options.
        bind_mounts.append(BindMount(orig_output_dir, OUTPUT_DATA_DIR, False))

    mount_opts = [bind_mount.mount_option_str for bind_mount in bind_mounts]

    return {
        'mount_opts': ' '.join(mount_opts),
        'translated_args': ' '.join(translated_args)
    }


def main():
    """Output mount options and translated cfs-config-util options in JSON format.

    Returns: None
    """
    results = process_file_options(sys.argv[1:])
    print(json.dumps(results, indent=2))
