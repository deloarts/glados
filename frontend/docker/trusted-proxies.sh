#!/bin/sh
# Writes the set_real_ip_from lines nginx.conf includes, one per entry of
# GLADOS_TRUSTED_PROXIES (comma or space separated addresses or CIDR
# networks). nginx takes the client address from X-Forwarded-For only when
# the connection comes from one of them. Unset, empty or "none" trusts no
# peer, so the client address is the TCP peer. The image's entrypoint runs
# this before nginx starts, without arguments; a malformed entry stops the
# container instead of silently trusting less or more than intended. The
# optional argument names another output file, for tests.
set -eu

conf=${1:-/etc/nginx/glados/trusted-proxies.conf}
proxies=$(printf '%s' "${GLADOS_TRUSTED_PROXIES:-}" | tr ',' ' ')

mkdir -p "$(dirname "$conf")"
: > "$conf"

if [ "$(printf '%s' "$proxies" | tr -d ' ')" = "none" ]; then
    proxies=""
fi

trusted=""
for proxy in $proxies; do
    case "$proxy" in
        *[!0-9A-Fa-f:./]*)
            echo "$0: GLADOS_TRUSTED_PROXIES entry '$proxy' is not an address or CIDR network" >&2
            exit 1
            ;;
    esac
    printf 'set_real_ip_from %s;\n' "$proxy" >> "$conf"
    trusted="${trusted:+$trusted, }$proxy"
done

echo "$0: trusting X-Forwarded-For from: ${trusted:-no peer}"
