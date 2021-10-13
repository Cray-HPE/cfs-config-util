#!/usr/bin/env bash
set -euo pipefail


export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
update-ca-certificates 2>/dev/null
exec /opt/venv/bin/cfs-config-util "$@"
