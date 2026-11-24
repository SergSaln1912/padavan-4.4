#!/bin/bash
# Обзор переноса DNSCrypt / DoH / DoT (stubby) из padavan-ng в padavan-4.4.
# Запуск на виртуальной машине:  bash port-survey-dns.sh > dns-survey.txt 2>&1
# Ничего не меняет, только читает деревья.
cd ~/prometeus/update || exit 1
NG=padavan-ng/trunk; N4=padavan-4.4/trunk
EX='--exclude-dir=.git --exclude=*.o --exclude=*.lo --exclude=*.a --exclude=*.so* --exclude=*.po --exclude=*.html --exclude=*.md --exclude=*.1 --exclude=*.3'
echo "##### 1. файлы ng, где упоминаются APP_DOH / APP_STUBBY / APP_DNSCRYPT / INCLUDE_*"
grep -rIl -E 'APP_(DOH|STUBBY|DNSCRYPT)|INCLUDE_(DOH|STUBBY|DNSCRYPT)' $NG $EX 2>/dev/null | grep -v -E '/configs/templates/' | head -40
echo; echo "##### 2. то же в 4.4"
grep -rIl -E 'APP_(DOH|STUBBY|DNSCRYPT)|INCLUDE_(DOH|STUBBY|DNSCRYPT)' $N4 $EX 2>/dev/null | grep -v -E '/configs/templates/' | head -40
echo; echo "##### 3. каталоги пакетов ng (user/ и libs/)"
ls -d $NG/user/{doh_proxy,dnscrypt-proxy,stubby,dnsproxy} $NG/libs/{libgetdns,libyaml,libunbound,libldns,libidn2,libev} 2>&1 | sed 's/^/  /'
echo "  --- в 4.4"
ls -d $N4/user/{doh_proxy,dnscrypt-proxy,stubby,dnsproxy} $N4/libs/{libgetdns,libyaml,libunbound,libldns,libidn2,libev} 2>&1 | sed 's/^/  /'
echo; echo "##### 4. содержимое user/doh_proxy, user/stubby, user/dnscrypt-proxy в ng (верхний уровень)"
for d in doh_proxy stubby dnscrypt-proxy; do echo "--- $d"; ls $NG/user/$d | head -15; done
echo; echo "##### 5. Makefile пакетов ng"
for d in doh_proxy stubby dnscrypt-proxy; do echo "--- $NG/user/$d/Makefile"; head -40 $NG/user/$d/Makefile 2>/dev/null; done
echo; echo "##### 6. скрипты запуска и правки в ng (user/scripts, user/rc, user/shared)"
grep -rIl -i -E 'doh_proxy|dnscrypt|stubby|doh_enable|dnscrypt_' $NG/user/scripts $NG/user/rc $NG/user/shared $NG/user/httpd $NG/user/www/n56u_ribbon_fixed $EX 2>/dev/null | head -40
echo; echo "##### 7. имена nvram-переменных doh_*, dnscrypt_*, stubby_* в ng (defaults.c)"
grep -n -E '"(doh_|dnscrypt_|stubby_)[a-z_0-9]*"' $NG/user/shared/defaults.c | cut -c1-120
echo; echo "##### 8. то же в 4.4 (defaults.c, variables.c)"
grep -n -E '"(doh_|dnscrypt_|stubby_)[a-z_0-9]*"' $N4/user/shared/defaults.c $N4/user/shared/variables.c 2>/dev/null | cut -c1-140 | head -30
echo; echo "##### 9. как ng запускает/останавливает сервисы (rc / services.c)"
grep -n -i -E 'doh|stubby|dnscrypt' $NG/user/rc/*.c $NG/user/rc/*.h 2>/dev/null | cut -c1-170 | head -40
echo; echo "##### 10. то же в 4.4"
grep -n -i -E 'doh|stubby|dnscrypt|dnsproxy' $N4/user/rc/*.c $N4/user/rc/*.h 2>/dev/null | cut -c1-170 | head -40
echo; echo "##### 11. user/Makefile: строки с этими пакетами (ng и 4.4)"
grep -n -i -E 'doh|stubby|dnscrypt|dnsproxy|getdns' $NG/user/Makefile | cut -c1-140
echo "--- 4.4"
grep -n -i -E 'doh|stubby|dnscrypt|dnsproxy|getdns' $N4/user/Makefile | cut -c1-140
echo; echo "##### 12. libs/Makefile: getdns и зависимости"
grep -n -i -E 'getdns|yaml|unbound|ldns|idn' $NG/libs/Makefile | cut -c1-140
echo "--- 4.4"
grep -n -i -E 'getdns|yaml|unbound|ldns|idn' $N4/libs/Makefile | cut -c1-140
echo; echo "##### 13. Config.in / Kconfig с этими флагами (ng и 4.4)"
grep -rn -E 'INCLUDE_(DOH|STUBBY|DNSCRYPT)' $NG/config $NG/Kconfig* $NG/user/Kconfig* $NG/../Kconfig* 2>/dev/null | head
echo "--- 4.4"
grep -rn -E 'INCLUDE_(DOH|STUBBY|DNSCRYPT)|INCLUDE_SMARTDNS' $N4/config $N4/Kconfig* $N4/user/Kconfig* $N4/../Kconfig* 2>/dev/null | head
echo; echo "##### 14. страницы ASP DoH/DoT/DNSCrypt: какие переменные и вызовы (4.4)"
for f in DNSCrypt DoH DoT; do echo "--- Advanced_Services_$f.asp"; grep -o -E '(nvram_get_x|nvram_get_f|nvram_get_list)\(""[ ]*,[ ]*"[a-z_0-9]+"|<% *[a-z_]+\([^)]*\) *; *%>|apply\.asp|rc_service[^<]*' $N4/user/www/n56u_ribbon_fixed/Advanced_Services_$f.asp 2>/dev/null | sort -u | head -30; done
echo; echo "ГОТОВО"
