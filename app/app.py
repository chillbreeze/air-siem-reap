#!/usr/bin/env python3
"""
Air Quality Dashboard Backend
Proxies requests to Home Assistant API and serves the static dashboard.
"""

import os
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, render_template_string
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


@app.route('/about/')
def about():
    """Serve the About page."""
    return send_from_directory('static/about', 'index.html')


@app.route('/contact/')
def contact():
    """Serve the Contact page."""
    return send_from_directory('static/contact', 'index.html')


@app.route('/sitemap.xml')
def sitemap():
    """Serve sitemap for search engine indexing."""
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://air.siemreap.cloud/</loc>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://air.siemreap.cloud/faq/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://air.siemreap.cloud/about/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>'''
    return app.response_class(xml, mimetype='application/xml')


@app.route('/api/sensors')
def get_sensors():
    """Fetch the most recent value for each sensor from InfluxDB."""
    data = {}

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            for key, (measurement, entity_id) in INFLUX_ENTITIES.items():
                if entity_id is None:
                    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["_field"] == "value")
  |> last()
'''
                else:
                    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")
  |> filter(fn: (r) => r["_field"] == "value")
  |> last()
'''
                result = qapi.query(query)
                for table in result:
                    for record in table.records:
                        data[key] = record.get_value()
    except Exception as e:
        app.logger.error(f'InfluxDB error in get_sensors: {e}')
        return jsonify({'error': 'Failed to fetch sensor data'}), 500

    return jsonify(data)


METRIC_META = {
    'aqi':         {'label': 'AQI',         'description': 'Live Air Quality Index readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'pm1':         {'label': 'PM 1.0',       'description': 'Live PM 1.0 particulate matter readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'pm25':        {'label': 'PM 2.5',       'description': 'Live PM 2.5 particulate matter readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'pm10':        {'label': 'PM 10',        'description': 'Live PM 10 particulate matter readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'temperature': {'label': 'Temperature',  'description': 'Live temperature readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'humidity':    {'label': 'Humidity',     'description': 'Live humidity readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'pressure':    {'label': 'Pressure',     'description': 'Live barometric pressure readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'heat_index':  {'label': 'Feels Like',   'description': 'Live heat index readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'dew_point':   {'label': 'Dew Point',    'description': 'Live dew point readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
    'voc':         {'label': 'VOC Index',    'description': 'Live VOC Index readings for Siem Reap, Cambodia. 24-hour charts and historical trends updated every 60 seconds.'},
}

BASE_URL = 'https://air.siemreap.cloud'

def _metric_comparison(entity_key):
    """Query InfluxDB for period-over-period averages for any metric.
    Returns dict keyed by 'day','week','month' with (direction, delta_pct) tuples.
    direction is 'up', 'down', 'similar', or None (insufficient data).
    """
    entry = INFLUX_ENTITIES.get(entity_key)
    if not entry:
        return {}
    measurement, entity_id = entry
    entity_filter = f'  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")\n' if entity_id else ''
    periods = [
        ('day',   '-24h', '-48h', '-24h'),
        ('week',  '-7d',  '-14d', '-7d'),
        ('month', '-30d', '-60d', '-30d'),
    ]
    results = {}
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            for period, curr_start, prev_start, prev_stop in periods:
                curr_q = f'''from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {curr_start})
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
{entity_filter}  |> filter(fn: (r) => r["_field"] == "value")
  |> mean()'''
                prev_q = f'''from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {prev_start}, stop: {prev_stop})
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
{entity_filter}  |> filter(fn: (r) => r["_field"] == "value")
  |> mean()'''
                curr_val = next((r.get_value() for t in qapi.query(curr_q) for r in t.records), None)
                prev_val = next((r.get_value() for t in qapi.query(prev_q) for r in t.records), None)
                if curr_val is None or prev_val is None or prev_val == 0:
                    results[period] = (None, None)
                else:
                    pct = (curr_val - prev_val) / prev_val * 100
                    if pct > 0:
                        results[period] = ('up', round(abs(pct)))
                    else:
                        results[period] = ('down', round(abs(pct)))
    except Exception as e:
        app.logger.error(f'Metric comparison error ({entity_key}): {e}')
        for period, *_ in periods:
            results.setdefault(period, (None, None))
    return results


@app.route('/metric/<entity_key>/')
def metric(entity_key):
    """Serve the metric history graph page with server-rendered OG tags."""
    meta = METRIC_META.get(entity_key, {'label': 'Air Quality', 'description': 'Live air quality readings for Siem Reap, Cambodia.'})

    cmp = _metric_comparison(entity_key)
    day_dir,   day_delta   = cmp.get('day',   (None, None))
    week_dir,  week_delta  = cmp.get('week',  (None, None))
    month_dir, month_delta = cmp.get('month', (None, None))

    template_path = os.path.join(app.root_path, 'static', 'metric', 'index.html')
    with open(template_path) as f:
        template_str = f.read()
    return render_template_string(
        template_str,
        og_title=f"{meta['label']} | Siem Reap Air Quality Monitor, Cambodia",
        og_description=meta['description'],
        og_url=f"{BASE_URL}/metric/{entity_key}/",
        og_image=f"{BASE_URL}/images/og-{entity_key}.png",
        day_direction=day_dir,
        day_delta=day_delta,
        week_direction=week_dir,
        week_delta=week_delta,
        month_direction=month_dir,
        month_delta=month_delta,
    )


@app.route('/api/history/<entity_key>')
def get_history(entity_key):
    """Fetch 24h of history for a sensor from InfluxDB."""
    entry = INFLUX_ENTITIES.get(entity_key)
    if not entry:
        return jsonify({'error': 'Unknown entity'}), 404

    measurement, entity_id = entry

    if entity_id is None:
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

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            result = qapi.query(query)

        points = []
        for table in result:
            for record in table.records:
                points.append({
                    'time': record.get_time().isoformat(),
                    'value': record.get_value(),
                })

        return jsonify(points)
    except Exception as e:
        app.logger.error(f'InfluxDB error for {entity_key}: {e}')
        return jsonify({'error': 'Failed to fetch history'}), 500


# (measurement, entity_id) — measurement is the unit label used by HA's InfluxDB integration
# AQI uses the full entity ID as measurement; others use their unit symbol
INFLUX_ENTITIES = {
    'aqi':         ('sensor.environmental_outdoor_sen55_aqi_outdoor', None),
    'pm1':         ('μg/m³', 'environmental_outdoor_sen55_pm1_0'),
    'pm25':        ('μg/m³', 'environmental_outdoor_sen55_pm2_5'),
    'voc':         ('sensor.environmental_outdoor_sen55_voc_index', None),
    'temperature': ('°C',    'environmental_outdoor_sen55_temperature'),
    'humidity':    ('%',     'environmental_outdoor_sen55_humidity'),
    'heat_index':  ('°C',    'environmental_outdoor_sen55_heat_index_outdoor'),
    'dew_point':   ('°C',    'environmental_outdoor_sen55_dew_point_outdoor'),
    'pressure':    ('hPa',   'bme688_pressure_indoor_01'),
}


@app.route('/api/history7d/<entity_key>')
def get_history7d(entity_key):
    """Fetch 7 days of daily high and low for a sensor from InfluxDB."""
    entry = INFLUX_ENTITIES.get(entity_key)
    if not entry:
        return jsonify({'error': 'Unknown entity'}), 404

    measurement, entity_id = entry

    if entity_id is None:
        base_query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["_field"] == "value")
'''
    else:
        base_query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")
  |> filter(fn: (r) => r["_field"] == "value")
'''

    max_query = base_query + '  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)'
    min_query = base_query + '  |> aggregateWindow(every: 1d, fn: min, createEmpty: false)'
    avg_query = base_query + '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            max_result = qapi.query(max_query)
            min_result = qapi.query(min_query)
            avg_result = qapi.query(avg_query)

        days = {}
        for table in max_result:
            for record in table.records:
                val = record.get_value()
                if val is None:
                    continue
                date = record.get_time().strftime('%Y-%m-%d')
                days.setdefault(date, {})['high'] = round(val, 1)

        for table in min_result:
            for record in table.records:
                val = record.get_value()
                if val is None:
                    continue
                date = record.get_time().strftime('%Y-%m-%d')
                days.setdefault(date, {})['low'] = round(val, 1)

        for table in avg_result:
            for record in table.records:
                val = record.get_value()
                if val is None:
                    continue
                date = record.get_time().strftime('%Y-%m-%d')
                days.setdefault(date, {})['avg'] = round(val, 1)

        points = [
            {'date': date, 'high': v['high'], 'low': v['low'], 'avg': v.get('avg')}
            for date, v in days.items()
            if 'high' in v and 'low' in v
        ]
        points.sort(key=lambda p: p['date'])
        return jsonify(points)
    except Exception as e:
        app.logger.error(f'InfluxDB 7d error for {entity_key}: {e}')
        return jsonify({'error': 'Failed to fetch 7-day history'}), 500


@app.route('/api/history30d/<entity_key>')
def get_history30d(entity_key):
    """Fetch 30 days of daily high, low, and avg for a sensor from InfluxDB."""
    entry = INFLUX_ENTITIES.get(entity_key)
    if not entry:
        return jsonify({'error': 'Unknown entity'}), 404

    measurement, entity_id = entry

    if entity_id is None:
        base_query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["_field"] == "value")
'''
    else:
        base_query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")
  |> filter(fn: (r) => r["_field"] == "value")
'''

    max_query = base_query + '  |> aggregateWindow(every: 1d, fn: max, createEmpty: false)'
    min_query = base_query + '  |> aggregateWindow(every: 1d, fn: min, createEmpty: false)'
    avg_query = base_query + '  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)'

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            max_result = qapi.query(max_query)
            min_result = qapi.query(min_query)
            avg_result = qapi.query(avg_query)

        days = {}
        for table in max_result:
            for record in table.records:
                val = record.get_value()
                if val is None:
                    continue
                date = record.get_time().strftime('%Y-%m-%d')
                days.setdefault(date, {})['high'] = round(val, 1)

        for table in min_result:
            for record in table.records:
                val = record.get_value()
                if val is None:
                    continue
                date = record.get_time().strftime('%Y-%m-%d')
                days.setdefault(date, {})['low'] = round(val, 1)

        for table in avg_result:
            for record in table.records:
                val = record.get_value()
                if val is None:
                    continue
                date = record.get_time().strftime('%Y-%m-%d')
                days.setdefault(date, {})['avg'] = round(val, 1)

        points = [
            {'date': date, 'high': v['high'], 'low': v['low'], 'avg': v.get('avg')}
            for date, v in days.items()
            if 'high' in v and 'low' in v
        ]
        points.sort(key=lambda p: p['date'])
        return jsonify(points)
    except Exception as e:
        app.logger.error(f'InfluxDB 30d error for {entity_key}: {e}')
        return jsonify({'error': 'Failed to fetch 30-day history'}), 500


@app.route('/api/heatmap/<entity_key>')
def get_heatmap(entity_key):
    """Fetch daily averages for a sensor from InfluxDB for a given year."""
    entry = INFLUX_ENTITIES.get(entity_key)
    if not entry:
        return jsonify({'error': 'Unknown entity'}), 404

    year = request.args.get('year', type=int, default=datetime.now().year)
    range_start = f'{year}-01-01T00:00:00Z'
    range_stop = f'{year + 1}-01-01T00:00:00Z'

    measurement, entity_id = entry

    if entity_id is None:
        query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {range_start}, stop: {range_stop})
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
'''
    else:
        query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {range_start}, stop: {range_stop})
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
'''

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            result = qapi.query(query)

        points = []
        for table in result:
            for record in table.records:
                val = record.get_value()
                if val is None:
                    continue
                points.append({
                    'date': record.get_time().strftime('%Y-%m-%d'),
                    'value': round(val, 1),
                })

        points.sort(key=lambda p: p['date'])
        return jsonify(points)
    except Exception as e:
        app.logger.error(f'InfluxDB heatmap error for {entity_key}: {e}')
        return jsonify({'error': 'Failed to fetch heatmap data'}), 500


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
    avg_query = query + '  |> mean()'

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            min_result = qapi.query(min_query)
            max_result = qapi.query(max_query)
            avg_result = qapi.query(avg_query)

            min_val = None
            max_val = None
            avg_val = None

            for table in min_result:
                for record in table.records:
                    min_val = record.get_value()

            for table in max_result:
                for record in table.records:
                    max_val = record.get_value()

            for table in avg_result:
                for record in table.records:
                    v = record.get_value()
                    avg_val = round(v, 1) if v is not None else None

        return jsonify({'min': min_val, 'max': max_val, 'avg': avg_val})
    except Exception as e:
        app.logger.error(f'InfluxDB error for {entity_key}: {e}')
        return jsonify({'error': 'Failed to fetch min/max'}), 500


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
