# Changelog

(C) Copyright 2021-2022 Hewlett Packard Enterprise Development LP.

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
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
