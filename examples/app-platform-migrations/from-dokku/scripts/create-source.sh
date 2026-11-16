#!/bin/bash
# Run on a fresh Dokku host with the copied example in EXAMPLE_DIR.
set -euo pipefail
: "${EXAMPLE_DIR:?Set EXAMPLE_DIR to the copied from-dokku example}"
: "${PRIVATE_DIR:?Set PRIVATE_DIR to a protected directory outside Git}"
umask 077
mkdir -p "$PRIVATE_DIR"
# Plugin installation creates shared executable files, not private exports.
(umask 022; dokku plugin:install https://github.com/dokku/dokku-postgres.git --committish 2.6.1 postgres) > "$PRIVATE_DIR/plugin-install.log" 2>&1
dokku apps:create portal
dokku config:set --no-restart --global HOST_CONFIG_SCOPE=global GLOBAL_ONLY_SETTING=preserved
dokku config:set --no-restart portal HOST_CONFIG_SCOPE=app NODE_ENV=production PORT=5000 WEB_CONCURRENCY=2 COOKIE_SECURE=false JOBS_PAUSED=true UPLOAD_DIR=/uploads
dokku postgres:create portal-db --image-version 17.11 --config-options '-c wal_level=logical -c max_replication_slots=4 -c max_wal_senders=8' > "$PRIVATE_DIR/database-create.log" 2>&1
dokku postgres:link portal-db portal > "$PRIVATE_DIR/database-link.log" 2>&1
install -d -o 1000 -g 1000 -m 0700 /var/lib/dokku/data/storage/portal
dokku storage:mount portal /var/lib/dokku/data/storage/portal:/uploads
dokku domains:set portal portal.example.com
dokku ports:set portal http:80:5000
tar -C "$EXAMPLE_DIR/app" --exclude=node_modules -cf "$PRIVATE_DIR/source-code.tar" .
# Source files must remain readable by the image's non-root runtime user.
(umask 022; dokku git:from-archive portal -- < "$PRIVATE_DIR/source-code.tar") > "$PRIVATE_DIR/deploy.log" 2>&1
dokku ps:scale portal web=1 worker=1
dokku config:export --global > "$PRIVATE_DIR/global.env"
dokku config:export portal > "$PRIVATE_DIR/app.env"
