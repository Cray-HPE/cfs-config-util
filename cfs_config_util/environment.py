"""
Environment variables used by cfs-config-util.

Copyright 2022 Hewlett Packard Enterprise Development LP
"""
import os

# TODO (CRAYSAT-898): Update default value following DNS changes
API_GW_HOST = os.environ.get('API_GW_HOST', 'api-gw-service-nmn.local')
API_CERT_VERIFY = os.environ.get('API_CERT_VERIFY', 'true').lower() == 'true'
API_TIMEOUT = int(os.environ.get('API_TIMEOUT', 60))
