#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Manages the launching, provisioning, and shutdown of android gce instances.

The script will either create the necessary gce instances and
connect them to adb, or shut them down and delete them.
"""

import argparse
import logging
import os
import psutil
import subprocess
import sys
import time

from android_gce import AndroidGCEInstance
from android_gce import AndroidGCEOperation
from googleapiclient.discovery import build
from oauth2client.client import GoogleCredentials

# Base local port to route adb traffic out of. Each instance needs its own
# corresponding local port, so this port gets incremented once for each one.
_BASE_PORT_SOURCE = 55560

_GCLOUD_PROJECT_NAME = 'google.com:chrome-android-cloud'
_ZONE = 'us-central1-f'
_SSH_KEY = '/tmp/ssh_android_gce_instance'

_ADB_CONNECT_RETRIES = 3

def launch(args, compute, instances):
  """Launches all instances."""
  logging.info("Deleting any old instances ...")
  delete_old_instances(compute, args.prefix)

  logging.info("Creating %d disks ..." % len(instances))
  wait_for_operations([instance.create_disk() for instance in instances])

  logging.info("Launching %d instances ..." % len(instances))
  wait_for_operations([instance.launch_instance() for instance in instances])

  logging.info("Waiting for vms to complete bootup process ...")
  while True:
    if all([instance.is_done_launching for instance in instances]):
      break
    time.sleep(5)

  logging.info("Finished launching vms")

  # Generate a temporary ssh key pair to communicate with the instances
  # that will be deleted and revoked at teardown
  generate_ssh_key()

  logging.info('Sending ssh keys ...')
  wait_for_operations([instance.send_ssh_key() for instance in instances])

  logging.info('Forwarding ports ...')
  for instance in instances:
    instance.forward_port()

  logging.info('Connecting adb to instances ...')
  for instance in instances:
    instance.connect_adb()

  logging.info('Rooting the instances ...')
  for instance in instances:
    instance.root_device()

  for i in xrange(_ADB_CONNECT_RETRIES):
    # Give a couple extra seconds for adbd on the instances to reboot. Unlike
    # devices connected via usb, they won't automatically reconnect with adb
    # after restarting.
    time.sleep(5)

    logging.info('Reconnecting adb to instances ...')
    if all([instance.connect_adb() for instance in instances]):
      break
  else:
    raise Exception('Unable to root the instances')

  logging.info('Setting properties on instances ...')
  for instance in instances:
    instance.set_props()

  logging.info('Unlocking screens ...')
  for instance in instances:
    instance.unlock_screen()

  logging.info('Successfully launched and setup instances!')


def shutdown(args, compute, instances):
  """Shuts down all instances."""
  logging.info('Killing port forwarding processes ...')
  for instance in instances:
    instance.kill_ssh_tunnel()

  logging.info('Removing temporary ssh key ...')
  clean_ssh_key()

  logging.info('Shutting down instances ...')
  operations = []
  for instance in instances:
    operations.append(instance.delete_instance())
  wait_for_operations(operations)

  logging.info('Successfully shutdown instances!')


def delete_old_instances(compute, instance_prefix):
  """Deletes any old instances that share the same prefix.

  This cleans up any instances that were spawned in a previous build
  that crashed and never managed to shut them down.
  """
  result = compute.instances().list(
      project=_GCLOUD_PROJECT_NAME,
      zone=_ZONE).execute()
  operations = []
  for instance in result.get('items', ()):
    if instance['name'].startswith(instance_prefix):
      logging.info('Deleting old instance: %s', instance['name'])
      operation = compute.instances().delete(project=_GCLOUD_PROJECT_NAME,
          zone=_ZONE, instance=instance['name']).execute()
      operations.append(AndroidGCEOperation(operation, compute,
          _ZONE, _GCLOUD_PROJECT_NAME, instance['name']))
  wait_for_operations(operations)


def generate_ssh_key():
  """Generates a temporary rsa keypair used to communicate with instances."""
  clean_ssh_key()
  cmd = ['ssh-keygen', '-P',  '', '-f', _SSH_KEY]
  subprocess.check_call(cmd)
  cmd = ['chmod', '400', _SSH_KEY]
  subprocess.check_call(cmd)
  cmd = ['chmod', '400', _SSH_KEY+'.pub']
  subprocess.check_call(cmd)


def clean_ssh_key():
  """Removes the temporary ssh key pair."""
  if os.path.exists(_SSH_KEY):
    os.unlink(_SSH_KEY)
  if os.path.exists(_SSH_KEY + '.pub'):
    os.unlink(_SSH_KEY + '.pub')


def wait_for_operations(operations):
  while True:
    if all([operation.is_complete for operation in operations]):
      return
    time.sleep(5)


def main(argv):
  parser = argparse.ArgumentParser(
    description='Launch or shutdown a specified number '
                'of Android images in GCE.'
  )
  parser.add_argument(
      'prefix',
      help='Prefix for the name of the disk and instance name. Needs '
           'to be unique per subordinate'
  )
  parser.add_argument('path_to_adb', type=str, help='Path to adb binary.')
  parser.add_argument(
      '--n',
      type=int,
      default=6,
      help='Number of VMs to launch or shutdown.'
  )
  subparsers = parser.add_subparsers(dest='command')

  subparser = subparsers.add_parser('launch')
  subparser.add_argument(
      '--snapshot',
      default='clean-17-l-phone-image-no-popups',
      help='Name of snapshot to create instance from.'
  )
  subparser.set_defaults(func=launch)

  subparser = subparsers.add_parser('shutdown')
  subparser.set_defaults(func=shutdown, snapshot=None)

  args = parser.parse_args()

  # Create a gce api object
  creds = GoogleCredentials.get_application_default()
  compute = build('compute', 'v1', credentials=creds)

  instances = []
  for i in xrange(args.n):
    instances.append(AndroidGCEInstance(
        project=_GCLOUD_PROJECT_NAME,
        zone=_ZONE,
        prefix='%s-%d' % (args.prefix, i),
        compute=compute,
        snapshot=args.snapshot,
        path_to_adb=args.path_to_adb,
        localport=_BASE_PORT_SOURCE + i,
        ssh_key_file=_SSH_KEY
    ))

  args.func(args, compute, instances)


if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO)
  main(sys.argv[1:])
