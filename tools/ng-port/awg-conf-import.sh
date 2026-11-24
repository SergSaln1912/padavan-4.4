#!/bin/sh
# Загрузка параметров AmneziaWG из .conf в nvram роутера (busybox sh).
# Использование на роутере:  sh awg-conf-import.sh /tmp/p.conf
# Записывает: Jc Jmin Jmax S1-S4 H1-H4 I1-I5 RandomTrailers DisableCookies ContentPaddingAddition
#             HeaderProtectionKey и прочие параметры AWG 3.1 из [Interface]/[Peer].
# Ключи, адреса, DNS, endpoint не трогает (их веб-страница сохраняет сама).
F="${1:-/tmp/p.conf}"
[ -s "$F" ] || { echo "нет файла: $F"; exit 1; }
n=0
setv() { nvram set "vpnc_awg_$1=$2" && n=$((n+1)) && echo "  $1 = $(printf %s "$2" | cut -c1-40)$( [ ${#2} -gt 40 ] && echo "... (${#2} симв.)")"; }
while IFS= read -r line || [ -n "$line" ]; do
	line=$(printf '%s' "$line" | tr -d '\r')
	case "$line" in \#*|\;*|\[*|"") continue ;; esac
	k="${line%%=*}"; v="${line#*=}"
	k=$(printf '%s' "$k" | tr -d ' \t' | tr 'A-Z' 'a-z')
	v=$(printf '%s' "$v" | sed 's/^[ \t]*//;s/[ \t]*$//')
	case "$k" in
		jc|jmin|jmax|s1|s2|s3|s4|h1|h2|h3|h4|i1|i2|i3|i4|i5|contentpaddingaddition|headerprotectionkey|\
		keepalivetimeout|maxhandshakeattempts|rekeyaftertime|rekeytimeout|rejectaftertime)
			setv "$k" "$v" ;;
		randomtrailers|disablecookies)
			case "$v" in on|ON|On|1|true|yes) v=1 ;; *) v=0 ;; esac
			setv "$k" "$v" ;;
	esac
done < "$F"
nvram commit
echo "записано параметров: $n (сохранено во флеш)"
echo "проверка: I1=$(nvram get vpnc_awg_i1 | wc -c) байт, jmin=$(nvram get vpnc_awg_jmin), jmax=$(nvram get vpnc_awg_jmax), cookies=$(nvram get vpnc_awg_disablecookies)"
echo "теперь: wgc.sh restart"
