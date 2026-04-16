#!/bin/sh
/usr/sbin/tailscaled --tun=userspace-networking --socks5-server=localhost:1055 &
sleep 2
tailscale up --authkey=$TAILSCALE_AUTHKEY --hostname=railway-api-$(hostname) --ephemeral
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
