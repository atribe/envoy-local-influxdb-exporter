#!/usr/bin/python
import os
import requests.exceptions
import time

from apcaccess import status as apc
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

def remove_irrelevant_data(status, remove_these_keys):
    for key in remove_these_keys:
        status.pop(key, None)

def move_tag_values_to_tag_dictionary(status, tags, tag_keys):
    for key in tag_keys:
        if key in status:
            tags[key] = status[key]
            status.pop(key, None)

def convert_numerical_values_to_floats(ups):
    for key in ups:
        if ups[key].replace('.', '', 1).isdigit():
            ups[key] = float(ups[key])

dbname = os.getenv('INFLUXDB_DATABASE', 'apcupsd')
user = os.getenv('INFLUXDB_USER')
password = os.getenv('INFLUXDB_PASSWORD')
port = os.getenv('INFLUXDB_PORT', 8086)
host = os.getenv('INFLUXDB_HOST')
apcupsd_host = os.getenv('APCUPSD_HOST', host)

min_delay = int(os.getenv('INTERVAL', 10))
max_delay = int(os.getenv('MAX_INTERVAL', min_delay * 8))
delay = min_delay

print_to_console = os.getenv('VERBOSE', 'false').lower() == 'true'

remove_these_keys = ['DATE', 'STARTTIME', 'END APC','ALARMDEL']
tag_keys = ['APC', 'HOSTNAME', 'UPSNAME', 'VERSION', 'CABLE', 'MODEL', 'UPSMODE', 'DRIVER', 'APCMODEL']

watts_key = 'WATTS'
nominal_power_key = 'NOMPOWER'

client = None

while True:
    if not client:
        try:
            client = InfluxDBClient(host, port, user, password, dbname)
            client.ping()
            print('Connectivity to InfluxDB present')
            dblist = client.get_list_database()
            if dbname not in [ x['name'] for x in dblist]:
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

    try:
        ups = apc.parse(apc.get(host=apcupsd_host), strip_units=True)

        remove_irrelevant_data(ups, remove_these_keys)

        tags = {'host': os.getenv('HOSTNAME', ups.get('HOSTNAME', 'apcupsd-influxdb-exporter'))}
        move_tag_values_to_tag_dictionary(ups, tags, tag_keys)

        convert_numerical_values_to_floats(ups)

        if watts_key not in os.environ and nominal_power_key not in ups:
            raise ValueError("Your UPS does not specify NOMPOWER, you must specify the max watts your UPS can produce.")

        ups[watts_key] = float(os.getenv('WATTS', ups.get('NOMPOWER'))) * 0.01 * float(ups.get('LOADPCT', 0.0))

        json_body = [
            {
                'measurement': 'apcaccess_status',
                'fields': ups,
                'tags': tags
            }
        ]

        if print_to_console:
            print(json_body)
            print(client.write_points(json_body))
        else:
            client.write_points(json_body)

    except ValueError as valueError:
        raise valueError
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.Timeout) as e:
        print(e)
        print('Resetting client connection')
        client = None
    except Exception as e:
        print(e)

    time.sleep(delay)
