#!/usr/bin/env python3
"""
Air Quality Dashboard Backend
Proxies requests to Home Assistant API and serves the static dashboard.
"""

import os
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, send_from_directory
import requests
from influxdb_client import InfluxDBClient

app = Flask(__name__, static_folder='static')

# Configuration from environment variables
HA_URL = os.environ.get('HA_URL', 'http://homeassistant.local:8123')
HA_TOKEN = os.environ.get('HA_TOKEN', '')

# InfluxDB configuration
INFLUX_URL = os.environ.get('INFLUX_URL', 'http://localhost:8086')
INFLUX_TOKEN = os.environ.get('INFLUX_TOKEN', '')
INFLUX_ORG = os.environ.get('INFLUX_ORG', '')
INFLUX_BUCKET = os.environ.get('INFLUX_BUCKET', 'home')

# Entity IDs - customize these to match your Home Assistant setup
ENTITIES = {
    'aqi': os.environ.get('ENTITY_AQI', 'sensor.air_quality_aqi'),
    'pm1': os.environ.get('ENTITY_PM1', 'sensor.air_quality_pm1'),
    'pm25': os.environ.get('ENTITY_PM25', 'sensor.air_quality_pm25'),
    'pm40': os.environ.get('ENTITY_PM40', 'sensor.air_quality_pm40'),
    'pm10': os.environ.get('ENTITY_PM10', 'sensor.air_quality_pm10'),
    'temperature': os.environ.get('ENTITY_TEMP', 'sensor.air_quality_temperature'),
    'humidity': os.environ.get('ENTITY_HUMIDITY', 'sensor.air_quality_humidity'),
    'heat_index': os.environ.get('ENTITY_HEAT_INDEX', 'sensor.air_quality_heat_index'),
    'dew_point': os.environ.get('ENTITY_DEW_POINT', 'sensor.air_quality_dew_point'),
    'pressure': os.environ.get('ENTITY_PRESSURE', 'sensor.air_quality_pressure'),
    'aqi_corrected': os.environ.get('ENTITY_AQI_CORRECTED', 'sensor.outdoor_pm2_5_corrected_aqi'),
}


def get_ha_state(entity_id):
    """Fetch the state of a single entity from Home Assistant."""
    headers = {
        'Authorization': f'Bearer {HA_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.get(
            f'{HA_URL}/api/states/{entity_id}',
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get('state')
    except requests.RequestException as e:
        app.logger.error(f'Error fetching {entity_id}: {e}')
        return None


@app.route('/')
def index():
    """Serve the main dashboard."""
    return send_from_directory('static', 'index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static/images', 'favicon.ico')


@app.route('/images/<path:filename>')
def images(filename):
    return send_from_directory('static/images', filename)


@app.route('/faq/')
def faq():
    """Serve the FAQ page."""
    return send_from_directory('static/faq', 'index.html')


@app.route('/api/sensors')
def get_sensors():
    """Fetch all sensor data from Home Assistant."""
    data = {}
    
    for key, entity_id in ENTITIES.items():
        state = get_ha_state(entity_id)
        if state is not None and state not in ('unknown', 'unavailable'):
            try:
                data[key] = float(state)
            except ValueError:
                data[key] = state
    
    return jsonify(data)


@app.route('/metric/<entity_key>/')
def metric(entity_key):
    """Serve the metric history graph page."""
    return send_from_directory('static/metric', 'index.html')


@app.route('/api/history/<entity_key>')
def get_history(entity_key):
    """Fetch 24h of history for a sensor from Home Assistant."""
    entity_id = ENTITIES.get(entity_key)
    if not entity_id:
        return jsonify({'error': 'Unknown entity'}), 404

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=24)

    headers = {
        'Authorization': f'Bearer {HA_TOKEN}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.get(
            f'{HA_URL}/api/history/period/{start.isoformat()}',
            headers=headers,
            params={
                'filter_entity_id': entity_id,
                'end_time': end.isoformat(),
                'minimal_response': True,
                'no_attributes': True,
            },
            timeout=30
        )
        response.raise_for_status()
        history = response.json()

        points = []
        if history and history[0]:
            for item in history[0]:
                try:
                    points.append({
                        'time': item['last_changed'],
                        'value': float(item['state'])
                    })
                except (ValueError, KeyError):
                    pass

        return jsonify(points)
    except requests.RequestException as e:
        app.logger.error(f'Error fetching history for {entity_id}: {e}')
        return jsonify({'error': 'Failed to fetch history'}), 500


# (measurement, entity_id) — measurement is the unit label used by HA's InfluxDB integration
# AQI uses the full entity ID as measurement; others use their unit symbol
INFLUX_ENTITIES = {
    'aqi':         ('sensor.environmental_outdoor_sen55_aqi_outdoor', None),
    'pm1':         ('μg/m³', 'environmental_outdoor_sen55_pm1_0'),
    'pm25':        ('μg/m³', 'environmental_outdoor_sen55_pm2_5'),
    'temperature': ('°C',    'environmental_outdoor_sen55_temperature'),
    'humidity':    ('%',     'environmental_outdoor_sen55_humidity'),
    'heat_index':  ('°C',    'environmental_outdoor_sen55_heat_index_outdoor'),
    'dew_point':   ('°C',    'environmental_outdoor_sen55_dew_point_outdoor'),
    'pressure':    ('hPa',   'bme688_pressure_indoor_01'),
}


@app.route('/api/minmax/<entity_key>')
def get_minmax(entity_key):
    """Fetch 24h min and max for a sensor from InfluxDB."""
    entry = INFLUX_ENTITIES.get(entity_key)
    if not entry:
        return jsonify({'error': 'Unknown entity'}), 404

    measurement, entity_id = entry

    if entity_id is None:
        # AQI: measurement IS the full entity ID, field is 'value'
        query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["_field"] == "value")
'''
    else:
        query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")
  |> filter(fn: (r) => r["_field"] == "value")
'''

    min_query = query + '  |> min()'
    max_query = query + '  |> max()'

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            min_result = qapi.query(min_query)
            max_result = qapi.query(max_query)

            min_val = None
            max_val = None

            for table in min_result:
                for record in table.records:
                    min_val = record.get_value()

            for table in max_result:
                for record in table.records:
                    max_val = record.get_value()

        return jsonify({'min': min_val, 'max': max_val})
    except Exception as e:
        app.logger.error(f'InfluxDB error for {entity_key}: {e}')
        return jsonify({'error': 'Failed to fetch min/max'}), 500


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
