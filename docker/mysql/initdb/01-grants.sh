#!/bin/bash
# Creates the least-privilege accounts with passwords from the environment.
set -euo pipefail
sed "s/'change-me'/'${HOMENEST_DB_PASSWORD}'/g" /docker-entrypoint-initdb.d/grants.sql.tpl \
  | mysql -uroot -p"${MYSQL_ROOT_PASSWORD}"
