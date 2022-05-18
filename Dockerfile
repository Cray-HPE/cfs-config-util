# Copyright 2021 Hewlett Packard Enterprise Development LP
#
# Dockerfile for cfs-config-util

FROM arti.dev.cray.com/baseos-docker-master-local/alpine:3.13.5

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY setup.py /sat/
COPY tools /sat/tools
COPY requirements.lock.txt /sat/requirements.txt
COPY README.md /sat/README.md
COPY CHANGELOG.md /sat/CHANGELOG.md
COPY cfs_config_util /sat/cfs_config_util
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh
ARG PIP_EXTRA_INDEX_URL="https://arti.dev.cray.com/artifactory/csm-python-modules-remote/simple"
RUN apk update && apk add --no-cache python3 git bash && \
    python3 -m venv $VIRTUAL_ENV && \
    pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir /sat/ && \
    rm -rf /sat/

ENTRYPOINT ["/entrypoint.sh"]
