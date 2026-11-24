#!/bin/sh
#
# Copyright (C) 2022 TurBoTse <860018505@qq.com>
#
#nvram set ntp_ready=0

mkdir -p /tmp/dnsmasq.dom
logger -t "autostart" "Creating /tmp/dnsmasq.dom/ to prevent dnsmasq start failure"

# ap relay monitor [simonchen]
if [ ! -x /etc/storage/sh_ezscript.sh ]; then
	cp /etc_ro/sh_ezscript.sh /etc/storage/sh_ezscript.sh
fi
if [ -x /etc/storage/ap_script.sh ]; then
	/etc/storage/ap_script.sh >/dev/null 2>&1 &
else
	cp /etc_ro/ap_script.sh /etc/storage/ap_script.sh
fi
smartdns_conf="/etc/storage/smartdns_custom.conf"
dnsmasq_Conf="/etc/storage/dnsmasq/dnsmasq.conf"
smartdns_Ini="/etc/storage/smartdns_conf.ini"
sdns_port=$(nvram get sdns_port)

logger -t "autostart" "Checking whether the router is connected to the Internet..."
count=0
while :
do
	ping -c 1 -W 1 -q 223.5.5.5 1>/dev/null 2>&1
	if [ "$?" == "0" ]; then
		break
	fi
	sleep 5
	ping -c 1 -W 1 -q baidu.com 1>/dev/null 2>&1
	if [ "$?" == "0" ]; then
		break
	fi
	sleep 5
	count=$((count+1))
	if [ $count -gt 18 ]; then
		break
	fi
done

if [ $(nvram get pppoemwan_enable) = 1 ] ; then
sleep 20
fi

if [ $(nvram get sqm_enable) = 1 ] ; then
sleep 30
logger -t "autostart" "Starting SQM QoS..."
/usr/lib/sqm/run.sh
fi

if [ $(nvram get adbyby_enable) = 1 ] ; then
logger -t "autostart" "Starting Adbyby plus..."
/usr/bin/adbyby.sh start
fi

if [ $(nvram get adg_enable) = 1 ] ; then
logger -t "autostart" "Starting AdGuard Home..."
/usr/bin/adguardhome.sh start
fi

if [ $(nvram get ss_enable) = 1 ] ; then
logger -t "autostart" "Starting proxy services..."
/usr/bin/shadowsocks.sh start
fi

if [ $(nvram get sdns_enable) = 1 ] ; then
   if [ -f "$smartdns_conf" ] ; then
       sed -i '/去广告/d' $smartdns_conf
       sed -i '/adbyby/d' $smartdns_conf
       sed -i '/no-resolv/d' "$dnsmasq_Conf"
       sed -i '/server=127.0.0.1#'"$sdns_portd"'/d' "$dnsmasq_Conf"
       sed -i '/port=0/d' "$dnsmasq_Conf"
       rm  -f "$smartdns_Ini"
   fi
logger -t "autostart" "Starting SmartDNS..."
/usr/bin/smartdns.sh start
fi

if [ $(nvram get aliddns_enable) = 1 ] ; then
logger -t "autostart" "Starting Aliyun DDNS..."
/usr/bin/aliddns.sh start
fi

if [ $(nvram get ddnsto_enable) = 1 ] ; then
logger -t "autostart" "Starting ddnsto..."
/usr/bin/ddnsto.sh start
fi

if [ $(nvram get aliyundrive_enable) = 1 ] ; then
logger -t "autostart" "Starting Aliyun Drive..."
/usr/bin/aliyundrive-webdav.sh start
fi

if [ $(nvram get zerotier_enable) = 1 ] ; then
logger -t "autostart" "Starting ZeroTier..."
/usr/bin/zerotier.sh start
fi

if [ $(nvram get wireguard_enable) = 1 ] ; then
logger -t "autostart" "Starting WireGuard..."
/usr/bin/wireguard.sh start
fi

if [ $(nvram get frpc_enable) = 1 ] ; then
logger -t "autostart" "Starting FRP client..."
/usr/bin/frp.sh start
fi
