#!/usr/bin/python
import datetime
import os
import time

import pytz
import requests
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from requests.auth import HTTPDigestAuth

array_group_dict = dict({
    '202014059854': 'West Array',
    '202014056703': 'Easy Array',
    '202014059616': 'West Array',
    '202014057857': 'West Array',
    '202014057689': 'South Array',
    '202014058289': 'South Array',
    '202014059871': 'West Array',
    '202014057752': 'South Array',
    '202014059244': 'South Array',
    '202014060736': 'East Array',
    '202014057830': 'South Array',
    '202014055874': 'East Array',
    '202014060275': 'West Array',
    '202014060045': 'South Array',
    '202014056109': 'South Array',
    '202014061347': 'South Array',
    '202014058701': 'South Array',
    '202014058911': 'South Array',
    '202014061631': 'South Array',
    '202015001261': 'West Array',
    '202014057141': 'West Array',
    '202014059119': 'East Array',
    '202014062034': 'West Array',
    '202014059113': 'West Array',
    '202014058930': 'East Array',
    '202014057147': 'West Array',
    '202014057758': 'East Array',
    '202014059912': 'West Array',
    '202014056831': 'South Array',
    '202014057187': 'West Array',
    '202014059979': 'East Array',
    '202014057959': 'East Array',
})

def convert_envoy_inverters_to_influxdb(inverter):
    tags = {
        'serialNumber': inverter['serialNumber'],
        'array': array_group_dict[inverter['serialNumber']]
    }
    fields = {
        'lastReportWatts': inverter['lastReportWatts'],
        'maxReportWatts': inverter['maxReportWatts']
    }

    tzinfo = pytz.timezone("America/Denver")
    measured_time = datetime.datetime.strptime(time.ctime(inverter['lastReportDate']),
                                               "%a %b %d %H:%M:%S %Y").astimezone(tzinfo)
    influx = {
        'measurement': 'inverters',
        'time': measured_time.isoformat(),
        'fields': fields,
        'tags': tags
    }

    return influx


dbname = os.getenv('INFLUXDB_DATABASE', 'envoy')
user = os.getenv('INFLUXDB_USER')
password = os.getenv('INFLUXDB_PASSWORD')
port = os.getenv('INFLUXDB_PORT', 8086)
host = os.getenv('INFLUXDB_HOST', 'influxdb.tribe3k.com')
envoy_host = os.getenv('ENVOY_HOST', 'http://envoy.tribe3k.com')

min_delay = int(os.getenv('INTERVAL', 300))
max_delay = int(os.getenv('MAX_INTERVAL', min_delay * 8))
delay = min_delay
print_to_console = 'true'
# print_to_console = os.getenv('VERBOSE', 'false').lower() == 'true'

client = None

while True:
    if not client:
        try:
            client = InfluxDBClient(host, port, user, password, dbname)
            client.ping()
            print('Connectivity to InfluxDB present')
            dblist = client.get_list_database()
            if dbname not in [x['name'] for x in dblist]:
                print("Database doesn't exist, creating")
                client.create_database(dbname)
            if delay != min_delay:
                delay = min_delay
                print('Connection successful, changing delay to %d' % delay)
        except Exception as e:
            if isinstance(e, InfluxDBClientError) and e.code == 401:
                print('Credentials provided are not authorized, error is: {}'.format(e.content))
            client = None
            new_delay = min(delay * 2, max_delay)
            if delay != new_delay:
                delay = new_delay
                print('Error creating client, changing delay to %d' % delay)

        # try:
    url = envoy_host + '/api/v1/production/inverters'
    envoy_response = requests.get(url, verify=False, auth=HTTPDigestAuth('envoy', '054903'))
    envoy = envoy_response.json()
    influxdb_body = list(map(convert_envoy_inverters_to_influxdb, envoy))

    # if print_to_console:
    #     print(client.write_points(json_body))
    # else:
    # print(influxdb_body)
    print(client.write_points(influxdb_body))

    # except ValueError as valueError:
    #     raise valueError
    # except (requests.exceptions.ConnectionError,
    #         requests.exceptions.HTTPError,
    #         requests.exceptions.Timeout) as e:
    #     print(e)
    #     print('Resetting client connection')
    #     client = None
    # except Exception as e:
    #     print(e)
    #
    time.sleep(delay)
