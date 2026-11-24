#!/bin/bash
# Обзор: shadowsocks (сделать необязательным), русский язык, IPSet, OpenVPN в padavan-ng (3.4) и padavan-4.4.
# Запуск на виртуальной машине:  bash port-survey-extras.sh > extras-survey.txt 2>&1
# Ничего не меняет, только читает деревья. Секретов в выводе нет.
cd ~/prometeus/update || exit 1
NG=padavan-ng/trunk; N4=padavan-4.4/trunk
EX='--exclude-dir=.git --exclude=*.o --exclude=*.lo --exclude=*.a --exclude=*.so* --exclude=*.po --exclude=*.html --exclude=*.md --exclude=*.1 --exclude=*.3'
CFG="$N4/configs/templates/RM2100.config"
sec() { printf '\n##### %s\n' "$*"; }

sec "A1. Флаги конфигурации профиля RM2100 в 4.4: shadowsocks / openvpn / ipset / dns"
grep -n -i -E 'SHADOWSOCKS|SSRUST|SS_RUST|V2RAY|XRAY|TROJAN|OPENVPN|IPSET|DNSCRYPT|DOH|STUBBY|SMARTDNS|ADBYBY|LANG' $CFG 2>&1 | head -40
sec "A2. Те же флаги в профиле роутера в ng (RM2100 / rm-ac2100)"
ls $NG/configs/templates/ 2>&1 | head -5
f=$(ls $NG/configs/templates/XIAOMI/rm-ac2100.config $NG/configs/templates/RM2100.config 2>/dev/null | head -1); echo "файл: $f"
grep -n -i -E 'SHADOWSOCKS|SSRUST|SS_RUST|V2RAY|XRAY|TROJAN|OPENVPN|IPSET|DNSCRYPT|DOH|STUBBY|SMARTDNS|LANG' "$f" 2>&1 | head -40

sec "B1. Shadowsocks в 4.4: флаги и места в коде"
grep -rIl -i -E 'shadowsocks|ss-redir|ss-local|ss_enable|ss-orig' $N4/user $N4/configs $N4/libs $EX 2>/dev/null | head -40
sec "B2. Как включается пакет: user/Makefile, cflags.mk, Kconfig (4.4)"
grep -n -i -E 'shadowsocks|ssrust' $N4/user/Makefile $N4/user/shared/cflags.mk $N4/Kconfig* $N4/config/* 2>/dev/null | cut -c1-160 | head -20
sec "B3. Страницы и ссылки меню для Shadowsocks (4.4): www, state.js, web_ex.c (found_app_*)"
grep -n -i -E 'shadowsocks' $N4/user/www/n56u_ribbon_fixed/state.js $N4/user/httpd/web_ex.c $N4/user/httpd/variables.c 2>/dev/null | cut -c1-170 | head -20

sec "C1. Языки интерфейса в 4.4: каталог словарей и список в UI"
ls $N4/user/www/dict 2>&1 | head -40
grep -n -E 'preferred_lang|LANG_|RU\b|"RU"' $N4/user/shared/defaults.c $N4/user/www/Makefile 2>/dev/null | cut -c1-160 | head -20
grep -n -i -E 'CONFIG_FIRMWARE_ENABLE_LANG|LANG' $CFG $N4/user/www/Makefile $N4/user/httpd/Makefile $N4/user/shared/cflags.mk 2>/dev/null | cut -c1-160 | head -20
sec "C2. Словари в ng: список и размеры (RU.dict против EN.dict)"
ls -la $NG/user/www/dict 2>&1 | head -40
sec "C3. Размер словарей в 4.4"
ls -la $N4/user/www/dict 2>&1 | head -40
sec "C4. Сколько строк-переводов в EN.dict против RU.dict (4.4 и ng)"
for t in $N4 $NG; do echo "== $t"; for l in EN RU; do printf '%s: ' $l; grep -c '=' $t/user/www/dict/$l.dict 2>/dev/null || echo нет; done; done

sec "D1. IPSet: каталоги и скрипты в ng"
ls -d $NG/user/ipset $NG/user/ipset-service $NG/user/scripts/ipset* $NG/libs/libipset 2>&1 | head
grep -rIl -i -E 'ipset_service|IPSET_SERVICE|ipset.sh|vpn.remote|IPSet' $NG/user $EX 2>/dev/null | head -20
sec "D2. IPSet: упоминания в 4.4"
grep -rIl -i -E 'ipset_service|IPSET_SERVICE|ipset.sh|IPSet' $N4/user $EX 2>/dev/null | head -20
ls -d $N4/user/ipset* $N4/libs/libipset 2>&1 | head
sec "D3. IPSet: страницы меню и переменные в ng (state.js, defaults.c)"
grep -n -i 'ipset' $NG/user/www/n56u_ribbon_fixed/state.js $NG/user/shared/defaults.c $NG/user/httpd/web_ex.c 2>/dev/null | cut -c1-150 | head -20
ls $NG/user/www/n56u_ribbon_fixed | grep -i -E 'ipset' | head

sec "E1. OpenVPN: пакеты, скрипты, страницы в 4.4"
ls -d $N4/user/openvpn* $N4/libs/lib{lzo,pkcs11}* 2>&1 | head
grep -rIl -i 'openvpn' $N4/user/rc $N4/user/shared $N4/user/httpd $N4/user/scripts $N4/user/www/n56u_ribbon_fixed $EX 2>/dev/null | head -30
sec "E2. OpenVPN в ng"
ls -d $NG/user/openvpn* $NG/libs/lib{lzo,pkcs11}* 2>&1 | head
grep -rIl -i 'openvpn' $NG/user/rc $NG/user/shared $NG/user/httpd $NG/user/scripts $NG/user/www/n56u_ribbon_fixed $EX 2>/dev/null | head -30
sec "E3. Флаги OpenVPN (cflags.mk, user/Makefile) в ng и 4.4"
grep -n -i 'openvpn' $NG/user/shared/cflags.mk $NG/user/Makefile 2>/dev/null | cut -c1-150 | head
echo "--- 4.4"
grep -n -i 'openvpn' $N4/user/shared/cflags.mk $N4/user/Makefile 2>/dev/null | cut -c1-150 | head
sec "E4. Страницы OpenVPN (сервер и клиент) в 4.4 и ng"
ls $N4/user/www/n56u_ribbon_fixed | grep -i -E 'openvpn|vpns|vpnc' | head
echo "--- ng"; ls $NG/user/www/n56u_ribbon_fixed | grep -i -E 'openvpn|vpns|vpnc' | head

echo; echo "ГОТОВО"
