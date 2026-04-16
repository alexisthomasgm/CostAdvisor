#!/bin/sh
/usr/sbin/tailscaled --tun=userspace-networking --socks5-server=localhost:1055 &
sleep 2
tailscale up --authkey=$TAILSCALE_AUTHKEY --hostname=railway-worker-$(hostname) --ephemeral
exec celery -A app.tasks worker --beat --loglevel=info
