#!/usr/bin/env python3
"""
Air Quality Dashboard Backend
Reads sensor data from InfluxDB and serves the dashboard pages and JSON API.
"""

import os
import time
from datetime import datetime
from flask import Flask, abort, jsonify, request, send_from_directory, render_template_string
from influxdb_client import InfluxDBClient

app = Flask(__name__, static_folder='static')

# InfluxDB configuration
INFLUX_URL = os.environ.get('INFLUX_URL', 'http://localhost:8086')
INFLUX_TOKEN = os.environ.get('INFLUX_TOKEN', '')
INFLUX_ORG = os.environ.get('INFLUX_ORG', '')
INFLUX_BUCKET = os.environ.get('INFLUX_BUCKET', 'home')

# How long (seconds) to reuse a query result before asking InfluxDB again.
# The sensor only reports once a minute, so there's no point querying more often.
CACHE_CURRENT = 30      # latest readings
CACHE_HISTORY = 300     # 24h / 7d / 30d charts and min/max
CACHE_SLOW = 3600       # heatmap and period comparisons

# Simple in-memory cache: {name: (time saved, result)}
_cache = {}


def cached(name, seconds, fetch):
    """Return the saved result for `name` if it's newer than `seconds`,
    otherwise call fetch() and save its result.
    If fetch() raises an error, nothing is saved, so the next request tries again."""
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < seconds:
        return hit[1]
    result = fetch()
    _cache[name] = (time.time(), result)
    return result


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


@app.route('/robots.txt')
def robots():
    """Point crawlers to the sitemap.
    No allow/block rules here: Cloudflare's managed robots.txt adds those in front of this file,
    and with no rules at all, everything is allowed anyway."""
    text = f"Sitemap: {BASE_URL}/sitemap.xml\n"
    return app.response_class(text, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap():
    """Serve sitemap for search engine indexing.
    Metric pages are listed automatically for every metric that has data in InfluxDB."""
    # (path, how often it changes, priority)
    pages = [
        ('/', 'hourly', '1.0'),
        ('/faq/', 'monthly', '0.7'),
        ('/about/', 'monthly', '0.6'),
    ]
    for key in METRIC_META:
        if key not in INFLUX_ENTITIES:
            continue  # page exists but has no data source (e.g. PM10), so don't list it
        pages.append((f'/metric/{key}/', 'hourly', '0.8'))

    urls = ''
    for path, freq, priority in pages:
        urls += f"""  <url>
    <loc>{BASE_URL}{path}</loc>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>
"""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>"""
    return app.response_class(xml, mimetype='application/xml')


@app.route('/api/sensors')
def get_sensors():
    """Return the most recent value for each sensor."""
    try:
        return jsonify(cached('sensors', CACHE_CURRENT, _fetch_sensors))
    except Exception as e:
        app.logger.error(f'InfluxDB error in get_sensors: {e}')
        return jsonify({'error': 'Failed to fetch sensor data'}), 500


def _fetch_sensors():
    """Get the latest value of every sensor with a single InfluxDB query."""
    # One condition per sensor, joined with "or", e.g.
    #   (r["_measurement"] == "°C" and r["entity_id"] == "..._temperature")
    conditions = []
    for measurement, entity_id in INFLUX_ENTITIES.values():
        if entity_id is None:
            conditions.append(f'r["_measurement"] == "{measurement}"')
        else:
            conditions.append(f'(r["_measurement"] == "{measurement}" and r["entity_id"] == "{entity_id}")')
    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => {" or ".join(conditions)})
  |> filter(fn: (r) => r["_field"] == "value")
  |> last()
'''

    # Lookup to turn each returned row back into our sensor key ('aqi', 'pm25', ...)
    key_for = {}
    for key, (measurement, entity_id) in INFLUX_ENTITIES.items():
        key_for[(measurement, entity_id)] = key

    data = {}
    newest = {}  # key -> time of the reading we kept, in case a sensor comes back in more than one table
    with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        for table in client.query_api().query(query):
            for record in table.records:
                measurement = record.get_measurement()
                key = key_for.get((measurement, record.values.get('entity_id'))) or key_for.get((measurement, None))
                if key is None or (key in newest and newest[key] >= record.get_time()):
                    continue
                newest[key] = record.get_time()
                data[key] = record.get_value()

    # Use the AQI reading's time as the "last updated" time,
    # so the page can tell when the outdoor sensor stops reporting
    if 'aqi' in newest:
        data['updated_at'] = newest['aqi'].isoformat()
    return data


METRIC_META = {
    'aqi':         {'label': 'AQI',         'description': 'Live Air Quality Index readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'pm1':         {'label': 'PM 1.0',       'description': 'Live PM 1.0 particulate matter readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'pm25':        {'label': 'PM 2.5',       'description': 'Live PM 2.5 particulate matter readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'pm10':        {'label': 'PM 10',        'description': 'Live PM 10 particulate matter readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'temperature': {'label': 'Temperature',  'description': 'Live temperature readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'humidity':    {'label': 'Humidity',     'description': 'Live humidity readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'pressure':    {'label': 'Pressure',     'description': 'Live barometric pressure readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'heat_index':  {'label': 'Feels Like',   'description': 'Live heat index readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'dew_point':   {'label': 'Dew Point',    'description': 'Live dew point readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'voc':         {'label': 'VOC Index',    'description': 'Live VOC Index readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
    'nox':         {'label': 'NOx Index',    'description': 'Live NOx Index readings for Siem Reap, Cambodia, updated every minute, with 24-hour charts and historical trends.'},
}

BASE_URL = 'https://air.siemreap.cloud'

def _metric_comparison(entity_key):
    """Period-over-period averages for any metric (cached for an hour).
    Returns dict keyed by 'day','week','month' with (direction, delta_pct) tuples.
    direction is 'up', 'down', 'similar', or None (insufficient data).
    """
    if entity_key not in INFLUX_ENTITIES:
        return {}
    try:
        return cached(f'comparison:{entity_key}', CACHE_SLOW, lambda: _fetch_comparison(entity_key))
    except Exception as e:
        app.logger.error(f'Metric comparison error ({entity_key}): {e}')
        return {'day': (None, None), 'week': (None, None), 'month': (None, None)}


def _fetch_comparison(entity_key):
    """Query InfluxDB for the averages behind _metric_comparison."""
    measurement, entity_id = INFLUX_ENTITIES[entity_key]
    entity_filter = f'  |> filter(fn: (r) => r["entity_id"] == "{entity_id}")\n' if entity_id else ''
    periods = [
        ('day',   '-24h', '-48h', '-24h'),
        ('week',  '-7d',  '-14d', '-7d'),
        ('month', '-30d', '-60d', '-30d'),
    ]
    results = {}
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
                if abs(pct) < 2:
                    # Tiny changes are just noise, so call them "similar" instead of showing ▲ 0% / ▼ 1%
                    results[period] = ('similar', 0)
                elif pct > 0:
                    results[period] = ('up', round(abs(pct)))
                else:
                    results[period] = ('down', round(abs(pct)))
    return results


@app.route('/metric/<entity_key>/')
def metric(entity_key):
    """Serve the metric history graph page with server-rendered OG tags."""
    # Only metrics with a data source get a page; anything else (typos, PM10) is a 404
    if entity_key not in INFLUX_ENTITIES:
        abort(404)
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

    # Average into 5-minute buckets (the chart shows 5-minute averages anyway),
    # so we send ~288 points instead of ~1440 raw readings.
    # timeSrc "_start" labels each bucket by its start time, same as the page's own bucketing.
    query += '  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false, timeSrc: "_start")\n'

    def fetch():
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            qapi = client.query_api()
            result = qapi.query(query)

        points = []
        for table in result:
            for record in table.records:
                points.append({
                    'time': record.get_time().isoformat(),
                    'value': round(record.get_value(), 2),
                })
        return points

    try:
        return jsonify(cached(f'history:{entity_key}', CACHE_HISTORY, fetch))
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
    'nox':         ('sensor.environmental_outdoor_sen55_nox_index', None),
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

    def fetch():
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
        return points

    try:
        return jsonify(cached(f'history7d:{entity_key}', CACHE_HISTORY, fetch))
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

    def fetch():
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
        return points

    try:
        return jsonify(cached(f'history30d:{entity_key}', CACHE_HISTORY, fetch))
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
    # Only allow sensible years, so random ?year= values can't fill up the cache
    if not 2020 <= year <= datetime.now().year:
        return jsonify({'error': 'Invalid year'}), 400
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

    def fetch():
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
        return points

    try:
        return jsonify(cached(f'heatmap:{entity_key}:{year}', CACHE_SLOW, fetch))
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

    def fetch():
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

        return {'min': min_val, 'max': max_val, 'avg': avg_val}

    try:
        return jsonify(cached(f'minmax:{entity_key}', CACHE_HISTORY, fetch))
    except Exception as e:
        app.logger.error(f'InfluxDB error for {entity_key}: {e}')
        return jsonify({'error': 'Failed to fetch min/max'}), 500


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
