# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file contains buildbucket service client."""

import datetime

from main import auth
from main import deferred_resource
from main.buildbucket import common

BUILDBUCKET_HOSTNAME_PRODUCTION = 'cr-buildbucket.appspot.com'
BUILDBUCKET_HOSTNAME_TESTING = 'cr-buildbucket-test.appspot.com'


def buildbucket_api_discovery_url(hostname=None):
  return (
      'https://%s/_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest' % hostname)


def get_default_buildbucket_hostname(main):
  return (
      BUILDBUCKET_HOSTNAME_PRODUCTION if main.is_production_host
      else BUILDBUCKET_HOSTNAME_TESTING)


def create_buildbucket_service(
    main, hostname=None, verbose=None):
  """Asynchronously creates buildbucket API resource.

  Returns:
    A DeferredResource as Deferred.
  """
  hostname = hostname or get_default_buildbucket_hostname(main)

  cred_factory = deferred_resource.CredentialFactory(
    lambda: auth.create_credentials_for_main(main),
    ttl=datetime.timedelta(minutes=5),
  )

  return deferred_resource.DeferredResource.build(
      'buildbucket',
      'v1',
      credentials=cred_factory,
      max_concurrent_requests=10,
      discoveryServiceUrl=buildbucket_api_discovery_url(hostname),
      verbose=verbose or False,
      log_prefix=common.LOG_PREFIX,
      timeout=60,
  )
