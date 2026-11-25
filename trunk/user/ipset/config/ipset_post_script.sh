#!/bin/sh
##
## fast download many cdn cidr:
##
## akamai, amazon, blizzard, cloudflare, clouvider, contabo
## datacamp, digitalocean, fastly, frantech, github, google
## hetzner, meta, oracle, ovh, reflected, sberbank, vultr
## telegram
##

angry_wget() {
  local r=1
  while [ $r -lt 10 ]; do
    if [ -x /usr/bin/curl ]; then # ng-port: curl
      curl -sSLkf --connect-timeout 10 -m 300 "$1" -o "$2" && return 0 || sleep $r
    else
      wget -T10 --no-check-certificate "$1" -O "$2" && return 0 || sleep $r
    fi
    r=$((r + 2))
  done
  return 1
}

cdn="https://github.com/nilabsent/ipset/archive/refs/heads/main.tar.gz"
angry_wget "$cdn" "-" | tar xz -C /tmp
for i in $(ls /tmp/ipset-main/ipv4/*.txt); do
    name="$(basename $i .txt)"
    ipset.sh import $name $i
done
rm -rf /tmp/ipset-main
