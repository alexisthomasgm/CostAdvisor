#!/bin/sh
/usr/sbin/tailscaled --tun=userspace-networking --socks5-server=localhost:1055 &
sleep 2
tailscale up --auth-key=$TAILSCALE_AUTHKEY --hostname=railway-worker-$(hostname)
exec celery -A app.tasks worker --beat --loglevel=info
