# API, worker and scheduler image. Based on the MySQL 8.4 image so the real
# mysqldump (not MariaDB's) is available for encrypted backups.
FROM mysql:8.4.6

RUN microdnf install -y python3.12 python3.12-pip && microdnf clean all \
 && useradd --system --create-home app && mkdir -p /data && chown app /data
WORKDIR /app
COPY backend/requirements.txt .
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt
COPY backend/ /app/
COPY db/ /db/
ENV PYTHONUNBUFFERED=1 APP_ENV=production
USER app
EXPOSE 8000
# the mysql base image's entrypoint starts a server; reset it
ENTRYPOINT []
CMD ["python3.12", "-m", "gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--access-logfile", "-", "wsgi:app"]
