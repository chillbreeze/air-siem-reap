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

Each metric on the home page is clickable and will show a 24-hour line graph of the metric. It is only updated every 5 minutes to smooth out the line to view the trends better.

## Why I Built It

Siem Reap has very little public air quality monitoring. During burning season the air gets noticeably bad, but there's not much data to back it up. I wanted real numbers from my own location. Once I had the sensor running in Home Assistant, building a public-facing site around it was the next step.

## Technical Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML / CSS / JavaScript |
| Backend | Python 3.12 + Flask + Gunicorn |
| Reverse proxy | Nginx |
| Containerization | Docker + Docker Compose |
| Data source | Home Assistant REST API |
| Sensor | SEN55 environmental sensor |
| Microcontroller | ESP32 C3 Mini | 

## Project Architecture

The Flask app polls Home Assistant's REST API on each request, applies PM2.5 correction algorithms, calculates derived metrics (heat index, dew point, AQI), and serves the dashboard. Everything runs in Docker on a local mini-PC server.

## Features

- Real-time AQI with PM2.5 correction
- Full environmental data: PM1.0, PM2.5, PM4.0, PM10, temperature, humidity, pressure
- Derived metrics: heat index, dew point
- Container health checks for reliability
- Sensor entities configurable via environment variables

---

**This is a personal portfolio project showcasing IoT, automation, and full-stack development skills.**
