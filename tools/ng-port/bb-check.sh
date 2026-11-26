#!/bin/sh
# Проверка BusyBox на роутере после прошивки образа с BusyBox 1.38 (и 1.24.x тоже годится для сравнения).
# Запуск на роутере:   sh /tmp/bb-check.sh 2>&1 | tee /tmp/bb-check.out
# Файл на роутер:      (на ПК)  scp bb-check.sh admin@192.168.1.1:/tmp/      (dropbear: без -O)
# Только чтение: ничего не меняет, кроме временных файлов /tmp/bbchk.*.

PASS=0; FAIL=0
ok()   { echo "PASS  $*"; PASS=$((PASS+1)); }
bad()  { echo "FAIL  $*"; FAIL=$((FAIL+1)); }
info() { echo "INFO  $*"; }
sect() { echo; echo "== $* =="; }

sect "1. Версия BusyBox"
VER=$(busybox 2>&1 | head -1)
info "$VER"
case "$VER" in *v1.38*) ok "BusyBox 1.38" ;; *v1.24*) info "это ещё 1.24 (образ без флага BUSYBOX_138?)" ;; *) bad "неожиданная версия" ;; esac
info "прошивка: $(nvram get firmver_sub 2>/dev/null) $(grep -m1 'firmware version' /tmp/syslog.log 2>/dev/null)"

sect "2. Апплеты, нужные прошивке"
LIST=$(busybox --list 2>/dev/null)
for a in udhcpc dhcp6c ntpd syslogd klogd crond nslookup wget nc ping ping6 traceroute ether-wake start-stop-daemon mount swapon swapoff mdev insmod rmmod modprobe; do
    echo "$LIST" | grep -qx "$a" && ok "апплет $a" || info "нет апплета $a"
done

sect "3. WAN по DHCP (udhcpc)"
W=$(nvram get wan0_ifname 2>/dev/null); [ -n "$W" ] || W=$(nvram get wan_ifname 2>/dev/null); [ -n "$W" ] || W=eth3
info "WAN интерфейс: $W"
ifconfig "$W" 2>/dev/null | grep -q "inet addr" && ok "WAN имеет адрес: $(ifconfig $W | grep 'inet addr' | sed 's/^ *//')" || bad "у $W нет IPv4"
ps | grep -v grep | grep -q "udhcpc" && ok "udhcpc запущен" || info "udhcpc не запущен (WAN не по DHCP или аренда уже получена и клиент завершён)"
ip route 2>/dev/null | grep -q "^default" && ok "маршрут по умолчанию: $(ip route | grep '^default' | head -1)" || bad "нет маршрута по умолчанию"
grep -E "DHCP WAN Client: bound" /tmp/syslog.log 2>/dev/null | tail -1 | sed 's/^/INFO  журнал: /'

sect "4. IPv6 (dhcp6c)"
ps | grep -v grep | grep -q "dhcp6c" && ok "dhcp6c запущен" || info "dhcp6c не запущен (IPv6 у провайдера нет или выключен)"
ip -6 addr 2>/dev/null | grep -c "scope global" | sed 's/^/INFO  глобальных IPv6-адресов: /'
grep -E "dhcp6c" /tmp/syslog.log 2>/dev/null | tail -2 | sed 's/^/INFO  журнал: /'

sect "5. Время (NTP)"
info "date: $(date)"
grep -E "NTP Client" /tmp/syslog.log 2>/dev/null | tail -2 | sed 's/^/INFO  журнал: /'
Y=$(date +%Y); [ "$Y" -ge 2026 ] 2>/dev/null && ok "год $Y (время синхронизировано)" || bad "год $Y: время не синхронизировано"

sect "6. wget по https (встроенный TLS BusyBox 1.38)"
rm -f /tmp/bbchk.https /tmp/bbchk.http
wget -T 20 -O /tmp/bbchk.https "https://raw.githubusercontent.com/nilabsent/padavan-ng/master/README.md" >/tmp/bbchk.wget.log 2>&1
RC=$?
SZ=$(wc -c < /tmp/bbchk.https 2>/dev/null)
if [ "$RC" = 0 ] && [ "${SZ:-0}" -gt 100 ]; then ok "wget https: rc=0, $SZ байт"
else bad "wget https: rc=$RC, размер ${SZ:-0}"; head -5 /tmp/bbchk.wget.log | sed 's/^/INFO  /'; fi
wget -T 20 -O /tmp/bbchk.http "http://neverssl.com/" >/tmp/bbchk.wget2.log 2>&1
[ -s /tmp/bbchk.http ] && ok "wget http: $(wc -c < /tmp/bbchk.http) байт" || bad "wget http не скачал файл"

sect "7. Скрипты прошивки: синтаксис (sh -n)"
NS=0; NF=0
for f in /usr/bin/*.sh /usr/sbin/*.sh /sbin/*.sh /bin/*.sh /etc_ro/*.sh /etc/storage/*.sh /etc/storage/*/*.sh /tmp/udhcpc.script; do
    [ -f "$f" ] || continue
    head -1 "$f" | grep -q "sh" || continue
    NS=$((NS+1))
    sh -n "$f" 2>/tmp/bbchk.err || { NF=$((NF+1)); bad "синтаксис: $f: $(head -1 /tmp/bbchk.err)"; }
done
[ "$NF" = 0 ] && ok "проверено скриптов: $NS, ошибок нет" || info "проверено скриптов: $NS, с ошибками: $NF"

sect "8. Журнал, cron, sysctl, утилиты"
logger -t bbchk "bb-check test message"; sleep 1
grep -q "bbchk: bb-check test message" /tmp/syslog.log 2>/dev/null && ok "syslogd пишет в /tmp/syslog.log" || bad "тестовое сообщение не попало в журнал"
ps | grep -v grep | grep -q "crond" && ok "crond запущен" || info "crond не запущен"
sysctl -q vm.drop_caches=3 2>/tmp/bbchk.err && ok "sysctl vm.drop_caches=3" || info "sysctl vm.drop_caches: $(head -1 /tmp/bbchk.err)"
echo "hello" | nc -w 2 127.0.0.1 9 >/dev/null 2>&1; nc --help 2>&1 | grep -q -- "-u" && ok "nc поддерживает -u" || info "nc без -u"
echo 'abc' | md5sum >/dev/null 2>&1 && ok "md5sum" || bad "md5sum"
nslookup localhost 127.0.0.1 >/dev/null 2>&1 && ok "nslookup через dnsmasq" || info "nslookup localhost не ответил"
info "память: $(free | sed -n 2p)"
info "uptime: $(uptime)"
dmesg 2>/dev/null | tail -3 | sed 's/^/INFO  dmesg: /'

sect "Итог"
echo "PASS=$PASS FAIL=$FAIL"
rm -f /tmp/bbchk.*
