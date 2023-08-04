# Changelog

(C) Copyright 2021-2023 Hewlett Packard Enterprise Development LP

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.3] - 2023-08-04

### Security
- Update oauthlib from 3.2.1 to 3.2.2 to address CVE-2022-36087.
- Update requests from 2.28.1 to 2.31.0 to address CVE-2023-32681.
- Update certifi from 2022.12.7 to 2023.7.22 to remove untrusted e-Tugra root
  certificates.

## [4.0.2] - 2023-08-02

### Changed
- Updated PyYAML to version 6.0.1, cray-product-catalog to 1.8.12, and
  csm-api-client to 1.1.5 in order to fix a build problem with earlier versions
  of PyYAML.

## [4.0.1] - 2023-01-13

### Security
- Update the version of certifi from 2022.9.14 to 2022.12.7 to resolve a
  medium-severity dependabot alert.

## [4.0.0] - 2022-10-05

### Changed
- Client code for accessing CSM has been factored out into the `csm-api-client`
  library. `cfs-config-util` now uses `csm-api-client` as a dependency for
  accessing CSM APIs. The Python modules
  `cfs_config_util.{cfs,vcs,session,apiclient}` have been removed and replaced
  with the corresponding modules in the `csm_api_client.service` package. The
  `cfs_config_util.bin.vcs_creds_helper` module has been removed.

## [3.3.1] - 2022-09-30

### Security
- Update the version of oauthlib from 3.1.1 to 3.2.1 to address
  CVE-2022-36087.

## [3.3.0] - 2022-08-17

### Changed
- The `--base-config`, `--base-file`, and `--base-query` options are no longer
  required. If they are not supplied, then `cfs-config-util` will start from an
  empty configuration, but overwriting existing configurations will be disabled.

### Fixed
- The `--help` text for `--base-config`, `--base-file`, and `--base-query` have
  been corrected. If a non-existent CFS configuration is given with
  `--base-config` or a non-existent file is given with `--base-file`, then an
  error will be displayed. Similarly, if no CFS configurations are found with
  `--base-query`, then an error will be displayed.

## [3.2.0] - 2022-08-09

### Added

- Added functionality which allows the `--playbook` command line argument to be
  used multiple times to specify multiple playbooks for the given product.
  A separate layer will be targeted for each given playbook.

## [3.1.1] - 2022-06-24

### Changed
- Changed the format of the license and copyright text in all of the source
  files.

## [3.1.0] - 2022-06-01

### Added

- Added a new entry point which just displays the help information for the options
  which will be exposed as options in a product's installer script that updates
  CFS configurations.
- Added a new entry point which pre-processes the options passed to the main
  entry point to determine which options refer to files and then outputs the
  mount options that should be passed to the container runtime and the translated
  arguments that refer to file paths as mounted inside the container.

## [3.0.1] - 2022-05-25

### Changed
- Made changes related to the open sourcing of cfs-config-util.
    - Update Jenkinsfile to use csm-shared-library.
    - Add Makefile for building container image and python package.
    - Pull base container image from external location.

## [3.0.0] - 2022-05-17

### Changed
- Changed the command-line arguments accepted by the `cfs-config-util` entry
  point to generalize this utility for use in other products and in other
  workflows. Includes the following functionality:
    - Options to specify base CFS configuration to be modified.
    - Options to control how the modified CFS configuration is saved.
    - Options to determine the contents of the layer to be added or removed.
- Generalize the `cfs_activate_version` and `cfs_deactivate_version` functions
  in the `activation` module to take HSM query parameters to find
  configurations, and a git commit or branch.
- Added a dependency on the `cray-product-catalog` Python package to support
  querying the product catalog K8s ConfigMap.

## [2.0.3] - 2022-04-13

### Changed
- Removed references to an unused internal pip repository from Dockerfile.

## [2.0.2] - 2022-02-24

### Removed
- Removed unnecessary ``nose`` and ``pycodestyle`` python packages from the
  locked production requirements file, ``requirements.lock.txt``, so they will
  not be included in the container image.

## [2.0.1] - 2022-02-23

### Added
- Add a warning log message when no CFS configuration is found that applies to
  nodes with role Management and subrole Master.
- Add an info log message that includes the contents of the layer that should be
  used in the CFS configurations when none are found.

## [2.0.0] - 2022-02-11

### Changed
- Changed how CFS configuration layers are identified by ``cfs_activate_version``
  and ``cfs_deactivate_version``.  Instead of being identified by name, they are
  identified by a combination of repository path (from the cloneUrl) and
  playbook.
- Removed layer name argument accepted by ``cfs_activate_version`` and
  ``cfs_deactivate_version``. Layer name is now generated from product and
  version.

## [1.0.0] - 2021-10-31

### Added

- Added ``cfs-config-util`` package for updating CFS configurations during
  install.
- Added ``Dockerfile`` for building a ``cfs-config-util`` image, and
  ``Jenkinsfile`` for building the image in a Jenkins pipeline.
