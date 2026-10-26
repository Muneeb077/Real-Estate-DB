# MySQL 8.4 LTS with the file keyring component (InnoDB TDE) and TLS-only connections.
# Build context is the repository root (see docker-compose.yml).
FROM mysql:8.4.6

# The global component manifest must sit next to the mysqld binary; the
# component's own config lives in the plugin directory.
COPY docker/mysql/mysqld.my /usr/sbin/mysqld.my
COPY docker/mysql/component_keyring_file.cnf /usr/lib64/mysql/plugin/component_keyring_file.cnf
COPY docker/mysql/homenest.cnf /etc/my.cnf.d/homenest.cnf
RUN mkdir -p /var/lib/mysql-keyring && chown mysql:mysql /var/lib/mysql-keyring && chmod 700 /var/lib/mysql-keyring

COPY docker/mysql/initdb/01-grants.sh /docker-entrypoint-initdb.d/01-grants.sh
COPY db/security/grants.sql /docker-entrypoint-initdb.d/grants.sql.tpl
COPY db/security/enable_tde.sql /docker-entrypoint-initdb.d/02-enable-tde.sql
