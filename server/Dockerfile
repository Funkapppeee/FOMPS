# OpenMPSync sync server - deploys identically on Oracle Always Free, any VPS,
# or a self-hoster's box.  Build from the repo root:
#   docker build -t openmpsync-server -f server/Dockerfile .
#   docker run -d --restart unless-stopped -p 8765:8765 -v omp-data:/data openmpsync-server
FROM python:3.12-slim

WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY openmpsync ./openmpsync
COPY server ./server

ENV OPENMPSYNC_DATA=/data OPENMPSYNC_KEEP=10 PORT=8765
VOLUME ["/data"]
EXPOSE 8765

# 1 worker + threads: requests that touch a world's manifest stay serialized
# (no cross-process race on the file store). The push conflict-guard is the real
# data-safety net regardless, so no save is ever clobbered.
CMD ["gunicorn", "--chdir", "/app", "--workers", "1", "--threads", "4", \
     "--bind", "0.0.0.0:8765", "--access-logfile", "-", "server.app:app"]
