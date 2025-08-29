#!/bin/sh
set -e

mkdir -p /var/log
flock -n /tmp/update-db.lock -c "
  python -u -m scripts.db_updater 2>&1 \
  | awk '{ print strftime(\"[%Y-%m-%d %H:%M:%S]\"), \$0 }' \
  | tee -a /var/log/db_updater.log \
  > /proc/1/fd/1
" 2> /proc/1/fd/2