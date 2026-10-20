[![Lighthouse Audit](https://github.com/chillbreeze/air-siem-reap/actions/workflows/lighthouse.yml/badge.svg)](https://github.com/chillbreeze/air-siem-reap/actions/workflows/lighthouse.yml)

# air.siemreap.cloud

A personal project demonstrating real-time air quality and climate monitoring for Siem Reap, Cambodia. This project showcases integration of IoT sensors, Home Assistant automation, and full-stack web development.

**Live:** [air.siemreap.cloud](https://air.siemreap.cloud)

<table>
  <tr>
    <td align="center"><img src="screenshots/aqi-website-screenshot-home.png" width="400" /><br/><sub>Home Page</sub></td>
    <td align="center"><img src="screenshots/aqi-website-screenshot-pm.png" width="400" /><br/><sub>PM 2.5</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshots/aqi-website-screenshot-humidity.png" width="400" /><br/><sub>Humidity</sub></td>
    <td align="center"><img src="screenshots/aqi-website-screenshot-faq.png" width="400" /><br/><sub>FAQ</sub></td>
  </tr>
</table>

---

## What It Does

Pulls live sensor data from a physical IoT sensor in my apartment, processes it through a Python backend, and displays it on a public-facing web dashboard. Anyone can check current PM2.5, temperature, humidity, and other environmental metrics for my location in Siem Reap.

Each metric on the home page is clickable and will show a 24-hour line graph of the metric. The sensor reports every 60 seconds; the chart averages readings into 5-minute points to smooth out the line and make trends easier to see.

## Why I Built It

Siem Reap has very little public air quality monitoring. During burning season the air gets noticeably bad, but there's not much data to back it up. I wanted real numbers from my own location. Once I had the sensor running in Home Assistant, building a public-facing site around it was the next step.

## Technical Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML / CSS / JavaScript, charts with Chart.js |
| Backend | Python 3.12 + Flask + Gunicorn |
| Reverse proxy | Nginx (behind Cloudflare for HTTPS) |
| Containerization | Docker + Docker Compose, managed with Dockge |
| Data source | InfluxDB, fed by Home Assistant's InfluxDB integration |
| Sensor | SEN55 environmental sensor (plus a BME688 indoors for pressure) |
| Microcontroller | ESP32 C3 Mini running ESPHome |

## Project Architecture

1. The ESP32 reads the SEN55 every 60 seconds. ESPHome also calculates AQI, heat index, and dew point on the device.
2. Home Assistant receives the readings and writes them to InfluxDB through its native InfluxDB integration.
3. The Flask app queries InfluxDB and serves a small JSON API (latest readings, 24-hour, 7-day, and 30-day history, and a yearly heatmap), plus the static pages.
4. The home page checks for new readings every 30 seconds.

Everything runs in Docker on a local mini-PC server. Python packages are installed once when the image is built (`app/Dockerfile`, versions pinned in `app/requirements.txt`). The app code is mounted into the container, so code changes only need a container restart; changing a package version needs a rebuild.

## Features

- Live AQI with a plain-language health tip for the current level
- Environmental data: PM1.0, PM2.5, VOC index, NOx index, temperature, humidity, heat index, dew point, and pressure
- Detail page for each metric with 24-hour, 7-day, and 30-day charts and a yearly heatmap
- "Sensor offline" warning on the home page when the newest reading is more than 15 minutes old
- Light and dark themes
- Container health checks for reliability

---

## Hardware Build

The outdoor sensor unit is built from off-the-shelf components and a 3D-printed enclosure.

**Components**

| Part | Details |
|------|---------|
| Microcontroller | Seeed Studio XIAO ESP32-C3 (`XIAO-ESP32-C3`) |
| Sensor | Sensirion SEN55-SDN-T (PM1.0, PM2.5, PM4.0, PM10, temperature, humidity) |
| Enclosure | 3D-printed SEN55 case by [Syvel Engineering](https://makerworld.com/en/models/893126-sen55-air-quality-sensor-case?from=search#profileId-850164) |
| Antenna | External 2.4GHz Wi-Fi antenna via U.FL connector |

**Assembly**

The enclosure STL files were printed by [3D Print Cambodia](https://www.facebook.com/3D.PRINT.Cambodia69/) in Phnom Penh, who were able to ship to Siem Reap at a very reasonable price.

The case was originally designed for an ESP8266 dev board, so the XIAO ESP32-C3 — being much smaller — needed a small dab of hot glue to stay in place. The SEN55 fits snugly in the left chamber, with the ESP32-C3 and antenna cable routed into the right side.

The XIAO ESP32-C3 has an external antenna connector, so a hole was punched through the top of the case using the awl on a Swiss Army knife to pass the antenna cable through. The finished unit is mounted to the wall outdoors with blue sticky tack.

<table>
  <tr>
    <td align="center"><img src="screenshots/project/project_1.jpg" width="380" /><br/><sub>Seeed Studio XIAO ESP32-C3</sub></td>
    <td align="center"><img src="screenshots/project/project_2.jpg" width="380" /><br/><sub>Punching the antenna hole with a Swiss Army knife awl</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshots/project/project_3.jpg" width="380" /><br/><sub>SEN55, ESP32-C3, and antenna inside the case</sub></td>
    <td align="center"><img src="screenshots/project/project_4.jpg" width="380" /><br/><sub>Finished unit mounted outdoors</sub></td>
  </tr>
</table>

---

**This is a personal portfolio project showcasing IoT, automation, and full-stack development skills.**
