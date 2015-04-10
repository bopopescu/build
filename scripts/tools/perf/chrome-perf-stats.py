#!/usr/bin/env python2.7
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to pull chromium.perf stats from chrome-infra-stats API.

Currently this just pulls success rates from the API, averages daily per
builder, and outputs a CSV. It could be improved to provide more detailed
success rates or build times.

The API documentation for chrome-infra-stats is at:
https://apis-explorer.appspot.com/apis-explorer/?
   base=https://chrome-infra-stats.appspot.com/_ah/api#p/
"""
import calendar
import csv
import json
import sys
import urllib
import urllib2

BUILDER_LIST_URL = ('https://chrome-infra-stats.appspot.com/'
                    '_ah/api/stats/v1/masters/chromium.perf')

BUILDER_STATS_URL = ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1/'
                     'stats/chromium.perf/%s/overall__build__result__/%s')

USAGE = 'Usage: chrome-perf-stats.py <outfilename> <year> <month> [<day>]'

if len(sys.argv) != 4 and len(sys.argv) != 5:
  print USAGE
  sys.exit(0)
outfilename = sys.argv[1]
year = int(sys.argv[2])
if year > 2016 or year < 2014:
  print USAGE
  sys.exit(0)
month = int(sys.argv[3])
if month > 12 or month <= 0:
  print USAGE
  sys.exit(0)
days = range(1, calendar.monthrange(year, month)[1] + 1)
if len(sys.argv) == 5:
  day = int(sys.argv[4])
  if day > 31 or day <=0:
    print USAGE
    sys.exit(0)
  days = [day]

response = urllib2.urlopen(BUILDER_LIST_URL)
builders = [builder['name'] for builder in json.load(response)['builders']]

success_rates = {}

for day in days:
  for hour in range(24):
    date_str = '%d-%02d-%02dT%02d:00Z' % (year, month, day, hour)
    date_dict_str = '%d-%02d-%02d' % (year, month, day)
    for builder in builders:
      url = BUILDER_STATS_URL % (urllib.quote(builder), urllib.quote(date_str))
      print url
      response = urllib2.urlopen(url)
      results = json.load(response)
      count = int(results['count'])
      if count == 0:
        continue
      success_count = count - int(results['failure_count'])
      success_rates.setdefault(date_dict_str, {})
      success_rates[date_dict_str].setdefault(builder, {
          'count': 0,
          'success_count': 0
      })
      success_rates[date_dict_str][builder]['count'] += count
      success_rates[date_dict_str][builder]['success_count'] += success_count

overall_success_rates = []
for day, results in success_rates.iteritems():
  success_rate_sum = 0
  success_rate_count = 0
  for builder, rates in results.iteritems():
    if rates['count'] == 0:
      continue
    success_rate_sum += (float(rates['success_count']) / float(rates['count']))
    success_rate_count += 1
  overall_success_rates.append(
      [day, float(success_rate_sum) / float(success_rate_count)])

  with open(outfilename, 'wb') as f:
    writer = csv.writer(f)
    writer.writerows(overall_success_rates)