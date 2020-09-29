#!/usr/bin/python
import datetime
import os
import time

import pytz
import requests
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from requests.auth import HTTPDigestAuth


def convert_envoy_inverters_to_influxdb(inverter):
    tags = {
        'serialNumber': inverter['serialNumber']
    }
    fields = {
        'lastReportWatts': inverter['lastReportWatts'],
        'maxReportWatts': inverter['maxReportWatts']
    }

    tzinfo = pytz.timezone("America/Denver")
    measured_time = datetime.datetime.strptime(time.ctime(inverter['lastReportDate']), "%a %b %d %H:%M:%S %Y").astimezone(tzinfo)
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

min_delay = int(os.getenv('INTERVAL', 10))
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

    print(influxdb_body)

    # if print_to_console:
    #     print(json_body)
    #     print(client.write_points(json_body))
    # else:
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
