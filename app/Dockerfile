# Dashboard image: packages are installed once at build time,
# so restarts are fast and don't depend on PyPI being reachable.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The app code itself is mounted from ./app in compose.yaml,
# so editing files only needs a container restart, not a rebuild.
CMD ["gunicorn", "--bind", "0.0.0.0:5080", "--workers", "2", "app:app"]
