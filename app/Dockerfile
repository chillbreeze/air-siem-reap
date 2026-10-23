# Dashboard image: packages are installed once at build time,
# so restarts are fast and don't depend on PyPI being reachable.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The app code itself is mounted from ./app in compose.yaml,
# so editing files only needs a container restart, not a rebuild.
# One worker with several threads, so all requests share the same in-memory cache in app.py
CMD ["gunicorn", "--bind", "0.0.0.0:5080", "--workers", "1", "--threads", "4", "app:app"]
