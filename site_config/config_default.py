# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Seeds a number of variables defined in chromium_config.py.

The recommended way is to fork this file and use a custom DEPS forked from
config/XXX/DEPS with the right configuration data."""

import os
import re
import socket


SERVICE_ACCOUNTS_PATH = '/creds/service_accounts'


class classproperty(object):
  """A decorator that allows is_production_host to only to be defined once."""
  def __init__(self, getter):
    self.getter = getter
  def __get__(self, instance, owner):
    return self.getter(owner)


class PortRange(object):
  def __init__(self, start, end):
    self.start = start
    self.end = end

  def compose_port(self, offset):
    ret = self.start + offset
    if not self.contains(ret):
      raise ValueError("Port offset %d must fit within range %d-%d" % (
          offset, self.start, self.end))
    return ret

  def contains(self, port):
    return port >= self.start and port <= self.end

  def offset_of(self, port):
    return port - self.start


class Main(object):
  # Repository URLs used by the SVNPoller and 'gclient config'.
  server_url = 'http://src.chromium.org'
  repo_root = '/svn'
  git_server_url = 'https://chromium.googlesource.com'

  # External repos.
  googlecode_url = 'http://%s.googlecode.com/svn'
  sourceforge_url = 'https://svn.code.sf.net/p/%(repo)s/code'
  googlecode_revlinktmpl = 'https://code.google.com/p/%s/source/browse?r=%s'

  # Directly fetches from anonymous Blink svn server.
  webkit_root_url = 'http://src.chromium.org/blink'
  nacl_trunk_url = 'http://src.chromium.org/native_client/trunk'

  llvm_url = 'http://llvm.org/svn/llvm-project'

  # Perf Dashboard upload URL.
  dashboard_upload_url = 'https://chromeperf.appspot.com'

  # Actually for Chromium OS subordinates.
  chromeos_url = git_server_url + '/chromiumos.git'

  # Default domain for emails to come from and
  # domains to which emails can be sent.
  main_domain = 'example.com'
  permitted_domains = ('example.com',)

  # Your smtp server to enable mail notifications.
  smtp = 'smtp'

  # By default, bot_password will be filled in by config.GetBotPassword().
  bot_password = None

  # Fake urls to make various factories happy.
  trunk_internal_url = None
  trunk_internal_url_src = None
  subordinate_internal_url = None
  git_internal_server_url = None
  syzygy_internal_url = None
  v8_internal_url = None


  class Base(object):
    """Main base template.
    Contains stubs for variables that all mains must define."""

    # Base service offset for 'main_port'
    MASTER_PORT_RANGE = PortRange(20000, 24999)
    # Base service offset for 'subordinate_port'
    SLAVE_PORT_RANGE = PortRange(30000, 34999)
    # Base service offset for 'main_port_alt'
    MASTER_PORT_ALT_RANGE = PortRange(25000, 29999)
    # Base service offset for 'try_job_port'
    TRY_JOB_PORT_RANGE = PortRange(50000, 54999)

    # A BuildBucket bucket to poll.
    buildbucket_bucket = None

    # Main address. You should probably copy this file in another svn repo
    # so you can override this value on both the subordinates and the main.
    main_host = 'localhost'
    @classproperty
    def current_host(cls):
      return socket.getfqdn()
    @classproperty
    def in_production(cls):
      return re.match(r'main.*\.golo\.chromium\.org', cls.current_host)
    # Only report that we are running on a main if the main_host (even when
    # main_host is overridden by a subclass) is the same as the current host.
    @classproperty
    def is_production_host(cls):
      return cls.current_host == cls.main_host

    # 'from:' field for emails sent from the server.
    from_address = 'nobody@example.com'
    # Additional email addresses to send gatekeeper (automatic tree closage)
    # notifications. Unnecessary for experimental mains and try servers.
    tree_closing_notification_recipients = []

    @classproperty
    def main_port(cls):
      return cls._compose_port(cls.MASTER_PORT_RANGE)

    @classproperty
    def subordinate_port(cls):
      # Which port subordinates use to connect to the main.
      return cls._compose_port(cls.SLAVE_PORT_RANGE)

    @classproperty
    def main_port_alt(cls):
      # The alternate read-only page. Optional.
      return cls._compose_port(cls.MASTER_PORT_ALT_RANGE)

    @classproperty
    def try_job_port(cls):
      return cls._compose_port(cls.TRY_JOB_PORT_RANGE)

    @classmethod
    def _compose_port(cls, service_range):
      """Returns: The port number for 'service' from the main's static config.

      Port numbers are mapped of the form:
      offset + YYZZ
      |        | \__The last two digits identify the main, e.g.
      |        |    main.chromium
      |        \____The second and third digits identify the main host, e.g.
      |             main1.golo
      \_____________The offset determines the port type, eg. main_port.  It
                    comes from the service_range.

      If any configuration is missing (incremental migration), this method will
      return '0' for that query, indicating no port.
      """
      return service_range.compose_port(
          (cls.main_port_base * 100) + # YY
          cls.main_port_id) # ZZ

    service_account_file = None

    @classproperty
    def service_account_path(cls):
      if cls.service_account_file is None:
        return None
      return os.path.join(SERVICE_ACCOUNTS_PATH, cls.service_account_file)

  ## Per-main configs.

  class Main1(Base):
    """Chromium main."""
    main_host = 'main1.golo.chromium.org'
    main_port_base = 1
    from_address = 'buildbot@chromium.org'
    tree_closing_notification_recipients = [
        'chromium-build-failure@chromium-gatekeeper-sentry.appspotmail.com']
    base_app_url = 'https://chromium-status.appspot.com'
    tree_status_url = base_app_url + '/status'
    store_revisions_url = base_app_url + '/revisions'
    last_good_url = base_app_url + '/lkgr'
    last_good_blink_url = 'http://blink-status.appspot.com/lkgr'

  class Main2(Base):
    """Legacy ChromeOS main."""
    main_host = 'main2.golo.chromium.org'
    main_port_base = 2
    tree_closing_notification_recipients = [
        'chromeos-build-failures@google.com']
    from_address = 'buildbot@chromium.org'

  class Main2a(Base):
    """Chromeos main."""
    main_host = 'main2a.golo.chromium.org'
    main_port_base = 15
    tree_closing_notification_recipients = [
        'chromeos-build-failures@google.com']
    from_address = 'buildbot@chromium.org'

  class Main3(Base):
    """Legacy client main."""
    main_host = 'main3.golo.chromium.org'
    main_port_base = 3
    tree_closing_notification_recipients = []
    from_address = 'buildbot@chromium.org'

  class Main3a(Base):
    """Client main."""
    main_host = 'main3a.golo.chromium.org'
    main_port_base = 13
    tree_closing_notification_recipients = []
    from_address = 'buildbot@chromium.org'

  class Main4(Base):
    """Try server main."""
    main_host = 'main4.golo.chromium.org'
    main_port_base = 4
    tree_closing_notification_recipients = []
    from_address = 'tryserver@chromium.org'
    code_review_site = 'https://codereview.chromium.org'

  class Main4a(Base):
    """Try server main."""
    main_host = 'main4a.golo.chromium.org'
    main_port_base = 14
    tree_closing_notification_recipients = []
    from_address = 'tryserver@chromium.org'
    code_review_site = 'https://codereview.chromium.org'

  ## Native Client related

  class NaClBase(Main3):
    """Base class for Native Client mains."""
    tree_closing_notification_recipients = ['bradnelson@chromium.org']
    base_app_url = 'https://nativeclient-status.appspot.com'
    tree_status_url = base_app_url + '/status'
    store_revisions_url = base_app_url + '/revisions'
    last_good_url = base_app_url + '/lkgr'
    perf_base_url = 'http://build.chromium.org/f/client/perf'

  ## ChromiumOS related

  class ChromiumOSBase(Main2):
    """Legacy base class for ChromiumOS mains"""
    base_app_url = 'https://chromiumos-status.appspot.com'
    tree_status_url = base_app_url + '/status'
    store_revisions_url = base_app_url + '/revisions'
    last_good_url = base_app_url + '/lkgr'

  class ChromiumOSBase2a(Main2a):
    """Base class for ChromiumOS mains"""
    base_app_url = 'https://chromiumos-status.appspot.com'
    tree_status_url = base_app_url + '/status'
    store_revisions_url = base_app_url + '/revisions'
    last_good_url = base_app_url + '/lkgr'
