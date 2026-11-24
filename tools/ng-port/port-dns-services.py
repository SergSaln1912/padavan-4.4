#!/usr/bin/env python3
"""
Перенос из padavan-ng в padavan-4.4: DNSCrypt (dnscrypt-proxy), DoT (stubby), DoH (https_dns_proxy).

Копирует пакеты и библиотеки, добавляет флаги сборки, rc-функции (запуск/остановка/перезапуск),
переменные nvram и обработчики httpd, страницы ASP, словари и подсказки, интеграцию с dnsmasq.
Каждая правка идемпотентна (повторный запуск ничего не дублирует) и отчитывается.

  python3 port-dns-services.py <путь_к_padavan-ng> <путь_к_padavan-4.4>

После запуска: включить в RM2100.config флаги CONFIG_FIRMWARE_INCLUDE_DNSCRYPT/STUBBY/DOH=y
(это делает правило 24 в port-build-fixes.py), пересобрать образ.
"""
import os, re, shutil, sys

if len(sys.argv) < 3: print(__doc__); sys.exit(1)
NG, N44 = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
for d in (NG, N44):
    if not os.path.isdir(os.path.join(d, "trunk")): print("ОШИБКА: нет %s/trunk" % d); sys.exit(1)

W = "trunk/user/www/n56u_ribbon_fixed"
results = []
def step(status, name): results.append((status, name)); print("%-13s %s" % (status, name))

def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape", newline="") as f: return f.read()
def wr(p, s):
    with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="") as f: f.write(s)
def load(root, rel):
    p = os.path.join(root, rel)
    if not os.path.exists(p): return None, False
    raw = rd(p); return raw.replace("\r\n", "\n"), ("\r\n" in raw)
def save(root, rel, s, crlf): wr(os.path.join(root, rel), s.replace("\n", "\r\n") if crlf else s)

def ins(rel, name, anchor, text, marker, where="after", occ=0, root=None):
    """Вставка text до/после совпадения anchor (регулярка, MULTILINE). Идемпотентно по marker."""
    root = root or N44
    s, crlf = load(root, rel)
    if s is None: step("НЕТ ФАЙЛА", "%s (%s)" % (name, rel)); return False
    if text is None: step("НЕТ В NG", name); return False
    if marker in s: step("уже есть", name); return True
    ms = list(re.finditer(anchor, s, re.M))
    if len(ms) <= occ: step("НЕ НАЙДЕНО", "%s: якорь %r (%s)" % (name, anchor[:60], rel)); return False
    m = ms[occ]; pos = m.end() if where == "after" else m.start()
    save(root, rel, s[:pos] + text + s[pos:], crlf); step("сделано", name); return True

def ng_block(rel, macro, nth=0):
    """Блок #if ... #endif из NG, первая строка которого содержит macro (с учётом вложенности)."""
    s, _ = load(NG, rel)
    if s is None: return None
    lines = s.split("\n"); found = 0
    for i, l in enumerate(lines):
        if re.match(r"\s*#\s*if\b", l) and macro in l:
            if found < nth: found += 1; continue
            depth = 0
            for j in range(i, len(lines)):
                if re.match(r"\s*#\s*if", lines[j]): depth += 1
                elif re.match(r"\s*#\s*endif", lines[j]):
                    depth -= 1
                    if depth == 0: return "\n".join(lines[i:j + 1]) + "\n"
            return None
    return None

def blocks(rel, macros, sep=""):
    parts = [ng_block(rel, m) for m in macros]
    return None if any(p is None for p in parts) else sep.join(parts)

M3 = ("APP_DOH", "APP_STUBBY", "APP_DNSCRYPT")
B3 = lambda rel: blocks(rel, M3)

# ================================================================ 1. пакеты и библиотеки
def copydir(rel):
    src, dst = os.path.join(NG, rel), os.path.join(N44, rel)
    if not os.path.isdir(src): step("НЕТ В NG", "каталог " + rel); return
    if os.path.isdir(dst): step("уже есть", "каталог " + rel); return
    shutil.copytree(src, dst, symlinks=True); step("сделано", "скопирован каталог " + rel)
    for dp, _, fs in os.walk(dst):
        if os.path.abspath(dp) != os.path.abspath(dst): continue
        for f in fs:
            if f == "Makefile":
                p = os.path.join(dp, f); s = rd(p)
                n = s.replace("$(ROOTDIR)/include/cross-mipsel-linux.cmake", "$(CONFIG_CMAKE_TOOLCHAIN_FILE)")
                if n != s: wr(p, n); step("сделано", "%s: cmake toolchain -> $(CONFIG_CMAKE_TOOLCHAIN_FILE)" % rel)
for d in ("trunk/user/doh_proxy", "trunk/user/stubby", "trunk/user/dnscrypt-proxy", "trunk/libs/libyaml", "trunk/libs/libgetdns"):
    copydir(d)
# cmake toolchain для libyaml, если там тоже используется
for rel in ("trunk/libs/libyaml/Makefile",):
    s, crlf = load(N44, rel)
    if s and "$(ROOTDIR)/include/cross-mipsel-linux.cmake" in s:
        save(N44, rel, s.replace("$(ROOTDIR)/include/cross-mipsel-linux.cmake", "$(CONFIG_CMAKE_TOOLCHAIN_FILE)"), crlf); step("сделано", "libyaml: cmake toolchain")

# libgetdns: поддержка libevent2 не нужна (stubby работает со стандартным циклом). В padavan-ng её находил CMake в stage с libevent 2.x,
# в 4.4 libevent другой (нет event2/event.h) и сборка падала на src/extension/libevent.c.
s, crlf = load(N44, "trunk/libs/libgetdns/Makefile")
if s is None: step("НЕТ ФАЙЛА", "libgetdns/Makefile")
elif "-DBUILD_LIBEVENT2=OFF" in s: step("уже есть", "libgetdns: -DBUILD_LIBEVENT2=OFF")
else:
    n = re.sub(r"^([ \t]*)-DENABLE_STATIC=ON[ \t]*\\\n", lambda m: m.group(0) + m.group(1) + "-DBUILD_LIBEVENT2=OFF \\\n", s, count=1, flags=re.M)
    if n == s: step("НЕ НАЙДЕНО", "libgetdns/Makefile: -DENABLE_STATIC=ON")
    else: save(N44, "trunk/libs/libgetdns/Makefile", n, crlf); step("сделано", "libgetdns: -DBUILD_LIBEVENT2=OFF")

# stubby: libgetdns при prefix=/ ставится в stage/usr/lib, а FindGetdns.cmake в кросс-режиме её не находит
# ("Could NOT find Getdns (missing: GETDNS_LIBRARIES)"). Передаём путь к библиотеке явно (stage/lib или stage/usr/lib).
s, crlf = load(N44, "trunk/user/stubby/Makefile")
if s is None: step("НЕТ ФАЙЛА", "stubby/Makefile")
elif "-DGETDNS_LIBRARY=" in s: step("уже есть", "stubby: -DGETDNS_LIBRARY")
else:
    n = re.sub(r"^([ \t]*)(-DCMAKE_TOOLCHAIN_FILE=)", lambda m: m.group(1) + "-DGETDNS_LIBRARY=$(firstword $(wildcard $(STAGEDIR)/lib/libgetdns.a $(STAGEDIR)/usr/lib/libgetdns.a)) \\\n" + m.group(1) + m.group(2), s, count=1, flags=re.M)
    if n == s: step("НЕ НАЙДЕНО", "stubby/Makefile: -DCMAKE_TOOLCHAIN_FILE")
    else: save(N44, "trunk/user/stubby/Makefile", n, crlf); step("сделано", "stubby: -DGETDNS_LIBRARY=<stage>/(usr/)lib/libgetdns.a")

# ================================================================ 2. флаги сборки
ins("trunk/user/shared/cflags.mk", "cflags.mk: -DAPP_DOH/-DAPP_STUBBY/-DAPP_DNSCRYPT",
    r"^ifeq \(\$\(CONFIG_FIRMWARE_INCLUDE_OPENVPN\),y\)\nCFLAGS \+= -DAPP_OPENVPN\nendif\n",
    "\nifeq ($(CONFIG_FIRMWARE_INCLUDE_DOH),y)\nCFLAGS += -DAPP_DOH\nendif\n"
    "\nifeq ($(CONFIG_FIRMWARE_INCLUDE_STUBBY),y)\nCFLAGS += -DAPP_STUBBY\nendif\n"
    "\nifeq ($(CONFIG_FIRMWARE_INCLUDE_DNSCRYPT),y)\nCFLAGS += -DAPP_DNSCRYPT\nendif\n", "-DAPP_DOH")

ins("trunk/user/Makefile", "user/Makefile: dnscrypt-proxy, stubby, doh_proxy",
    r"^dir_\$\(CONFIG_FIRMWARE_INCLUDE_OPENVPN\)[ \t]+\+= openvpn\n",
    "dir_$(CONFIG_FIRMWARE_INCLUDE_DNSCRYPT)\t\t+= dnscrypt-proxy\ndir_$(CONFIG_FIRMWARE_INCLUDE_STUBBY)\t\t+= stubby\n"
    "dir_$(CONFIG_FIRMWARE_INCLUDE_DOH)\t\t+= doh_proxy\n", "+= dnscrypt-proxy")

LM = "trunk/libs/Makefile"
ins(LM, "libs/Makefile: значения по умолчанию LIBGETDNS/LIBYAML", r"^LIBS_INCLUDE_LIBCURL=n\n",
    "LIBS_INCLUDE_LIBGETDNS=n\nLIBS_INCLUDE_LIBYAML=n\n", "LIBS_INCLUDE_LIBGETDNS=n")
ins(LM, "libs/Makefile: зависимости Stubby/DoH/DNSCrypt",
    r"^ifeq \(\$\(CONFIG_FIRMWARE_INCLUDE_OPENVPN\),y\)\nLIBS_INCLUDE_LIBLZO=y\nendif\n",
    "ifeq ($(CONFIG_FIRMWARE_INCLUDE_STUBBY),y)\nLIBS_INCLUDE_LIBYAML=y\nLIBS_INCLUDE_LIBGETDNS=y\nendif\n"
    "ifeq ($(CONFIG_FIRMWARE_INCLUDE_DOH),y)\nLIBS_INCLUDE_LIBCURL=y\nLIBS_INCLUDE_LIBCARES=y\nLIBS_INCLUDE_LIBEV=y\nendif\n"
    "ifeq ($(CONFIG_FIRMWARE_INCLUDE_DNSCRYPT),y)\nLIBS_INCLUDE_LIBSODIUM=y\nendif\n", "LIBS_INCLUDE_LIBGETDNS=y")
ins(LM, "libs/Makefile: каталоги libyaml и libgetdns (после libssl)", r"^dir_y[ \t]+\+= libssl\n",
    "dir_$(LIBS_INCLUDE_LIBYAML)\t\t\t+= libyaml\ndir_$(LIBS_INCLUDE_LIBGETDNS)\t\t\t+= libgetdns\n", "+= libgetdns")

# ================================================================ 3. rc: функции запуска/остановки
RS = "trunk/user/rc/services.c"
fn_blocks = blocks(RS, M3)
ins(RS, "services.c: is_/start_/stop_/restart_ для DoH, DoT, DNSCrypt", r"^#if defined\(APP_SCUT\)\n", fn_blocks, "int is_doh_run(void)", where="before")
ins(RS, "services.c: остановка DoH/DoT/DNSCrypt в stop_services", r"^#if defined\(APP_FRP\)\n\tstop_frp\(\);\n#endif\n",
    "/* ng-port: DNS-прокси */\n#if defined(APP_DOH)\n\tstop_doh();\n#endif\n#if defined(APP_STUBBY)\n\tstop_stubby();\n#endif\n#if defined(APP_DNSCRYPT)\n\tstop_dnscrypt();\n#endif\n", "ng-port: DNS-прокси")
ins("trunk/user/rc/rc.h", "rc.h: прототипы DoH/DoT/DNSCrypt", r"^#if defined\(APP_WIREGUARD\)\n", B3("trunk/user/rc/rc.h"),
    "int is_doh_run(void);", where="before")
ins("trunk/user/shared/notify_rc.h", "notify_rc.h: RCN_RESTART_DOH/STUBBY/DNSCRYPT", r'^#define RCN_RESTART_SSHD.*\n',
    '#define RCN_RESTART_DOH\t\t\t"restart_doh"\n#define RCN_RESTART_STUBBY\t\t"restart_stubby"\n#define RCN_RESTART_DNSCRYPT\t\t"restart_dnscrypt"\n',
    "RCN_RESTART_DOH")

RC = "trunk/user/rc/rc.c"
ins(RC, "rc.c: запуск DoH/DoT/DNSCrypt при старте", r"^#if defined ?\(APP_SMBD\) \|\| defined ?\(APP_NMBD\)\n\tstart_wins\(\);\n#endif\n",
    "\n#if defined(APP_DOH)\n\tstart_doh();\n#endif\n#if defined(APP_STUBBY)\n\tstart_stubby();\n#endif\n#if defined(APP_DNSCRYPT)\n\tstart_dnscrypt();\n#endif\n",
    "\tstart_doh();")
hdl = "".join(
    "#if defined(%s)\n\t\telse if (strcmp(entry->d_name, %s) == 0)\n\t\t{\n\t\t\t%s();\n\t\t}\n#endif\n" % t
    for t in (("APP_DOH", "RCN_RESTART_DOH", "restart_doh"), ("APP_STUBBY", "RCN_RESTART_STUBBY", "restart_stubby"),
              ("APP_DNSCRYPT", "RCN_RESTART_DNSCRYPT", "restart_dnscrypt")))
ins(RC, "rc.c: обработчики уведомлений restart_doh/stubby/dnscrypt",
    r"^\t\telse if \(strcmp\(entry->d_name, RCN_RESTART_SSHD\) == 0\)\n\t\t\{\n\t\t\trestart_sshd\(\);\n\t\t\}\n(?:#endif\n)?", hdl,
    "RCN_RESTART_DOH) == 0")
ins(RC, "rc.c: перезапуск dnsmasq при смене времени (NTP)",
    r"^\t\telse if \(strcmp\(entry->d_name, RCN_RESTART_NTPC\) == 0\)\n\t\t\{\n\t\t\tnotify_watchdog_time\(\);\n",
    "#if defined(APP_DNSCRYPT) || defined(APP_STUBBY) || defined(APP_DOH)\n"
    "\t\t\t// updating time servers records in dnsmasq for ntp bypassing DoT/DoH/DNSCrypt\n"
    "\t\t\tif (nvram_match(\"dnscrypt_enable\", \"1\")\n\t\t\t\t|| nvram_match(\"stubby_enable\", \"1\")\n\t\t\t\t|| nvram_match(\"doh_enable\", \"1\"))\n"
    "\t\t\t{\n\t\t\t\trestart_dhcpd();\n\t\t\t}\n#endif\n", "updating time servers records in dnsmasq")

ins("trunk/user/rc/net_lan.c", "net_lan.c: перезапуск DoH/DoT/DNSCrypt вместе с dnsmasq", r"^\tstart_dns_dhcpd\(is_ap_mode\);\n",
    "\n#if defined(APP_DOH)\n\trestart_doh();\n#endif\n#if defined(APP_STUBBY)\n\trestart_stubby();\n#endif\n#if defined(APP_DNSCRYPT)\n\trestart_dnscrypt();\n#endif\n",
    "\trestart_doh();")
ins("trunk/user/rc/watchdog.c", "watchdog.c: перезапуск после смены времени более суток",
    r'^\t\tlogmessage\("NTP Client", "System time changed, offset: %ss", offset\);\n',
    "\t\tif (atoi(offset) > 86400) { /* more than one day */\n\t\t\tnotify_rc(RCN_RESTART_DOH);\n\t\t\tnotify_rc(RCN_RESTART_STUBBY);\n\t\t\tnotify_rc(RCN_RESTART_DNSCRYPT);\n\t\t}\n",
    "notify_rc(RCN_RESTART_DOH)")

SU = "trunk/user/shared/shutils.c"
dc = [ng_block(SU, "APP_DNSCRYPT", i) for i in range(3)]
ins(SU, "shutils.c: пользователь dnscrypt в /etc/passwd", r'^.*"sshd", 100, 99.*\n', dc[0], 'fprintf(fp1, "%s:x:%d:%d::%s:%s\\n", "dnscrypt"')
ins(SU, "shutils.c: пользователь dnscrypt не удаляется при сохранении", r'^[ \t]*strcmp\(usernm, "sshd"\)\) \{\n', dc[1], 'strcmp(usernm, "dnscrypt")', where="before")
ins(SU, "shutils.c: dnscrypt в /etc/shadow", r'^.*"sshd", "\*", 16000.*\n', dc[2], '"dnscrypt", "*", 16000')

# ================================================================ 4. dnsmasq (services_ex.c)
SX = "trunk/user/rc/services_ex.c"
ng_sx, _ = load(NG, SX)
dns_chunk = None; resolv_chunk = None
if ng_sx:
    m = re.search(r"^\t\tno_resolv = 0;\n.*?(?=^#if defined\(APP_TOR\))", ng_sx, re.M | re.S)
    if m: dns_chunk = "\n\t\t/* don't use resolv-file to resolve DNS queries if doh_proxy, stubby or dnscrypt-proxy is enabled */\n" + m.group(0)
    m = re.search(r"^\t\tif \(no_resolv\)\n\t\t\{\n.*?\n\t\t\}\n", ng_sx, re.M | re.S)
    if m: resolv_chunk = m.group(0)
s44, c44 = load(N44, SX)
if s44 is not None and "no_resolv" not in s44:
    ok = True
    s = s44
    a = 'const char *storage_dir = "/etc/storage/dnsmasq";\n'
    i = s.find(a, s.find("start_dns_dhcpd(int is_ap_mode)"))
    if i < 0: ok = False; step("НЕ НАЙДЕНО", "services_ex.c: объявления в start_dns_dhcpd")
    else:
        s = s[:i + len(a)] + "\tint no_resolv;\n\tchar nvram_key[32];\n\tchar *ipaddr_t, *dnsproxy_listen_addr, *srv_addr[2];\n" + s[i + len(a):]
        a2 = '\tipaddr  = nvram_safe_get("lan_ipaddr");\n'
        j = s.find(a2, i)
        if j < 0: ok = False; step("НЕ НАЙДЕНО", "services_ex.c: ipaddr = nvram_safe_get(lan_ipaddr)")
        else:
            s = s[:j + len(a2)] + '\tipaddr_t = nvram_safe_get("lan_ipaddr_t");\n\tif (strlen(ipaddr_t) < 7) ipaddr_t = ipaddr;\n' + s[j + len(a2):]
            a3 = '\t\tfprintf(fp, "listen-address=%s\\n", ipaddr);\n'
            k = s.find(a3, j)
            if k < 0 or not dns_chunk or not resolv_chunk: ok = False; step("НЕ НАЙДЕНО", "services_ex.c: listen-address / блоки DNS в NG")
            else:
                s = s[:k + len(a3)] + dns_chunk.rstrip("\n") + "\n" + resolv_chunk + s[k + len(a3):]
    if ok: save(N44, SX, s, c44); step("сделано", "services_ex.c: dnsmasq использует DoH/DoT/DNSCrypt (no-resolv, обход для NTP)")
elif s44 is not None: step("уже есть", "services_ex.c: интеграция dnsmasq")

# ================================================================ 5. httpd
CH = "trunk/user/httpd/common.h"
s, crlf = load(N44, CH)
if s is not None and "EVM_RESTART_DOH" not in s:
    used = {int(n) for l in s.split("\n") if l.startswith("#define EVM_") for n in re.findall(r"<<\s*(\d+)", l) if int(n) < 64}
    free = [i for i in range(64) if i not in used]
    print("Занятые биты EVM_*:", sorted(used)); print("Свободные биты:", free)
    names = ("DOH", "STUBBY", "DNSCRYPT")
    if len(free) < 3:
        step("ВНИМАНИЕ", "свободных битов EVM_* только %d из 3: недостающие совместно используют бит %s" % (len(free), free[-1] if free else "?"))
        free = free + [free[-1]] * (3 - len(free)) if free else [0, 0, 0]
    evm = "".join("#define EVM_RESTART_%s\t\t(1ULL << %d)\n" % (n, b) for n, b in zip(names, free[:3]))
    evt = "".join("#define EVT_RESTART_%s\t\t1\n" % n for n in names)
    ins(CH, "common.h: EVM_RESTART_DOH/STUBBY/DNSCRYPT (биты %s)" % free[:3], r"^#define EVM_RESTART_SQM.*\n", evm, "EVM_RESTART_DOH")
    ins(CH, "common.h: EVT_RESTART_DOH/STUBBY/DNSCRYPT", r"^#define EVT_RESTART_SQM.*\n", evt, "EVT_RESTART_DOH")
else: step("уже есть" if s is not None else "НЕТ ФАЙЛА", "common.h: EVM/EVT для DoH/DoT/DNSCrypt")

VR = "trunk/user/httpd/variables.c"
# первые блоки в NG — списки переменных (вторые — строки таблицы событий); берём блоки, внутри которых есть {"имя", "", NULL, ...}
def var_block(macro):
    s, _ = load(NG, VR)
    for n in range(4):
        b = ng_block(VR, macro, n)
        if b and '{"' in b and "EVM_RESTART_" in b and "RCN_" not in b: return b
    return None
def evt_block(macro):
    for n in range(4):
        b = ng_block(VR, macro, n)
        if b and "RCN_RESTART_" in b: return b
    return None
vars_txt = None
parts = [var_block(m) for m in M3]
if all(parts): vars_txt = "".join(parts)
# Переменные должны быть в таблице variables_LANHostConfig (страницы шлют sid_list=LANHostConfig;General;Storage;), как в NG.
# В таблице FirewallConfig они молча не сохраняются (веб "Применить" возвращает прежнее значение).
def vars_table(txt, name):
    m = re.search(r"struct variable %s\[\] = \{\n" % name, txt)
    if not m: return None
    e = txt.find("{0,0,0,0}", m.end())
    return (m.end(), e) if e > 0 else None
s, crlf = load(N44, VR)
if s is None: step("НЕТ ФАЙЛА", VR)
elif vars_txt is None: step("НЕТ В NG", "variables.c: переменные doh_*/stubby_*/dnscrypt_*")
else:
    fw, lan = vars_table(s, "variables_FirewallConfig"), vars_table(s, "variables_LANHostConfig")
    if not fw or not lan: step("НЕ НАЙДЕНО", "variables.c: таблицы FirewallConfig/LANHostConfig")
    else:
        changed = False
        # миграция: блок, вставленный ранее в FirewallConfig, убираем
        if '{"doh_enable"' in s[fw[0]:fw[1]]:
            seg = s[fw[0]:fw[1]]
            if vars_txt in seg: s = s[:fw[0]] + seg.replace(vars_txt, "", 1) + s[fw[1]:]; changed = True; step("сделано", "variables.c: переменные DNS убраны из FirewallConfig")
            else: step("ВНИМАНИЕ", "variables.c: doh_* в FirewallConfig не совпадает с NG, уберите вручную")
            lan = vars_table(s, "variables_LANHostConfig")
        if '{"doh_enable"' in s[lan[0]:lan[1]]: step("уже есть", "variables.c: переменные DoH/DoT/DNSCrypt в LANHostConfig")
        else:
            m = re.search(r'^\t\t\t\{"sshd_enable", "", NULL, [^\n]*\n(?:\t\t\t\{"sshd_enable_gp"[^\n]*\n)?', s[lan[0]:lan[1]], re.M)
            if not m: step("НЕ НАЙДЕНО", "variables.c: якорь sshd_enable в LANHostConfig")
            else:
                pos = lan[0] + m.end(); s = s[:pos] + vars_txt + s[pos:]; changed = True; step("сделано", "variables.c: переменные doh_*/stubby_*/dnscrypt_* (LANHostConfig)")
        if changed: save(N44, VR, s, crlf)
ev = "".join(evt_block(m) or "" for m in M3)
ins(VR, "variables.c: события перезапуска DoH/DoT/DNSCrypt", r"^\t\t\{EVM_RESTART_SSHD,[^\n]*\n(?:#endif\n)?", ev or None, "EVM_RESTART_DOH,")

ins("trunk/user/httpd/web_ex.c", "web_ex.c: found_app_doh/stubby/dnscrypt (объявления)",
    r"^#if defined ?\(APP_SSHD\)\n\tint found_app_sshd = 1;\n#else\n\tint found_app_sshd = 0;\n#endif\n",
    "".join("#if defined(%s)\n\tint found_app_%s = 1;\n#else\n\tint found_app_%s = 0;\n#endif\n" % (m, n, n)
            for m, n in (("APP_DOH", "doh"), ("APP_QUIC", "quic"), ("APP_STUBBY", "stubby"), ("APP_DNSCRYPT", "dnscrypt"))), "int found_app_doh")
ins("trunk/user/httpd/web_ex.c", "web_ex.c: found_app_* в javascript-функциях (формат)",
    r'^\t\t"function found_app_sshd\(\) \{ return %d;\}\\n"\n',
    '\t\t"function found_app_doh() { return %d;}\\n"\n\t\t"function found_app_quic() { return %d;}\\n"\n\t\t"function found_app_stubby() { return %d;}\\n"\n\t\t"function found_app_dnscrypt() { return %d;}\\n"\n',
    "function found_app_doh()")
ins("trunk/user/httpd/web_ex.c", "web_ex.c: found_app_* в javascript-функциях (аргументы)", r"^\t\tfound_app_sshd,\n",
    "\t\tfound_app_doh,\n\t\tfound_app_quic,\n\t\tfound_app_stubby,\n\t\tfound_app_dnscrypt,\n", "\t\tfound_app_doh,")
ins("trunk/user/httpd/web_ex.c", "web_ex.c: отдача dnscrypt-resolvers.csv", r'^\t\{ "restore_st\.cgi\*".*\n',
    "#if defined(APP_DNSCRYPT)\n\t/* DNSCrypt proxy resolvers file */\n\t{ \"**.csv\", \"text/csv\", NULL, NULL, do_file, 0 },\n#endif\n", '"**.csv"')

DF = "trunk/user/shared/defaults.c"
dv = "".join(ng_block(DF, m) or "" for m in M3)
ins(DF, "defaults.c: значения по умолчанию doh_*/stubby_*/dnscrypt_*", r'^\t\{ "preferred_lang", "[A-Z]*" \},\n', dv or None, '{ "doh_enable"')

# ================================================================ 6. www
WM = "trunk/user/www/Makefile"
ins(WM, "www/Makefile: удалять страницы DoH/DoT/DNSCrypt, если не включены", r"^ifneq \(\$\(CONFIG_FIRMWARE_INCLUDE_SMARTDNS\),y\)\n\trm -f \$\(INSTALLDIR\)/www/Advanced_smartdns\.asp\nendif\n",
    "ifneq ($(CONFIG_FIRMWARE_INCLUDE_DNSCRYPT),y)\n\trm -f $(INSTALLDIR)/www/Advanced_Services_DNSCrypt.asp\nendif\n"
    "ifneq ($(CONFIG_FIRMWARE_INCLUDE_DOH),y)\n\trm -f $(INSTALLDIR)/www/Advanced_Services_DoH.asp\nendif\n"
    "ifneq ($(CONFIG_FIRMWARE_INCLUDE_STUBBY),y)\n\trm -f $(INSTALLDIR)/www/Advanced_Services_DoT.asp\nendif\n", "Advanced_Services_DoH.asp")
ins(WM, "www/Makefile: ссылка dnscrypt-resolvers.csv", r"^\tcd \$\(ROMFS_DIR\)/www && ln -sf /opt/share/www/custom custom\n",
    "ifeq ($(CONFIG_FIRMWARE_INCLUDE_DNSCRYPT),y)\n\tcd $(ROMFS_DIR)/www && ln -sf /usr/share/dnscrypt-proxy/dnscrypt-resolvers.csv dnscrypt-resolvers.csv\nendif\n",
    "dnscrypt-resolvers.csv")

pages = ("Advanced_Services_DNSCrypt", "Advanced_Services_DoH", "Advanced_Services_DoT")
sj, _ = load(N44, W + "/state.js")
menu21 = bool(sj and "Advanced_Services_DoH.asp" in sj)
for pg in pages:
    rel = "%s/%s.asp" % (W, pg)
    if os.path.exists(os.path.join(N44, rel)): step("уже есть", "страница " + pg + ".asp")
    elif os.path.exists(os.path.join(NG, rel)):
        s, _ = load(NG, rel)
        if menu21: s = re.sub(r"show_menu\(\s*5\s*,\s*7\s*,\s*(\d+)\s*\)", r"show_menu(5,21,\1)", s)
        wr(os.path.join(N44, rel), s); step("сделано", "скопирована страница %s.asp%s" % (pg, " (меню «Сервисы»)" if menu21 else ""))
    else: step("НЕТ В NG", "страница " + pg)
if not menu21: step("ВНИМАНИЕ", "в state.js 4.4 нет вкладок «Сервисы» (DoH...): их добавляет port-phase2b.py; страницы без него не видны в меню")

# словари и подсказки: ключи <#...#> страниц + блоки helpcontent
used_keys = set(); tips = set()
for pg in pages:
    s, _ = load(N44, "%s/%s.asp" % (W, pg))
    if s: used_keys |= set(re.findall(r"<#([A-Za-z0-9_]+)#>", s)); tips |= {int(x) for x in re.findall(r"openTooltip\(\s*this\s*,\s*(\d+)\s*,", s)}
ngh, _ = load(NG, W + "/help.js"); h44, hc = load(N44, W + "/help.js")
if ngh and h44 and tips:
    blk = lambda t: {int(m.group(1)): m.group(0) for m in re.finditer(r"^helpcontent\[(\d+)\]\s*=\s*new Array\(.*?\);\n", t, re.M | re.S)}
    nb, hb = blk(ngh), blk(h44)
    norm = lambda t: re.sub(r"\s+", "", t)
    maxn = max(list(hb) + list(nb) + [0])
    remap = {}; add = []
    for n in sorted(tips):
        if n not in nb: step("ВНИМАНИЕ", "подсказка helpcontent[%d] не найдена в help.js padavan-ng" % n); continue
        if n in hb and norm(hb[n]) == norm(nb[n]): continue
        if n in hb: maxn += 1; remap[n] = maxn
        add.append((remap.get(n, n), re.sub(r"^helpcontent\[\d+\]", "helpcontent[%d]" % remap.get(n, n), nb[n])))
    if add:
        s = h44; anchor = re.search(r"^function openTooltip", s, re.M)
        if anchor:
            if "<<ng-dns>>" not in s:
                body = "// ng-port: подсказки DoH/DoT/DNSCrypt\n" + "\n".join(t for _, t in add) + "\n"
                save(N44, W + "/help.js", s[:anchor.start()] + body + s[anchor.start():], hc); step("сделано", "help.js: +%d подсказок DoH/DoT/DNSCrypt %s" % (len(add), "(номера сдвинуты: %s)" % remap if remap else ""))
                used_keys |= set(re.findall(r"<#([A-Za-z0-9_]+)#>", body))
        else: step("НЕ НАЙДЕНО", "help.js: function openTooltip")
    if remap:
        for pg in pages:
            rel = "%s/%s.asp" % (W, pg); s, c = load(N44, rel)
            if s:
                n2 = re.sub(r"(openTooltip\(\s*this\s*,\s*)(\d+)(\s*,)", lambda m: m.group(1) + str(remap.get(int(m.group(2)), int(m.group(2)))) + m.group(3), s)
                if n2 != s: save(N44, rel, n2, c); step("сделано", "%s.asp: номера подсказок перенумерованы" % pg)
def parse_dict(path):
    d = {}
    if os.path.exists(path):
        for l in rd(path).replace("\r\n", "\n").split("\n"):
            m = re.match(r"^([A-Za-z0-9_]+)=", l)
            if m: d[m.group(1)] = l
    return d
dng, d44 = os.path.join(NG, "trunk/user/www/dict"), os.path.join(N44, "trunk/user/www/dict")
if os.path.isdir(dng) and os.path.isdir(d44):
    for fn in sorted(os.listdir(d44)):
        ngd = parse_dict(os.path.join(dng, fn))
        if not ngd: continue
        p = os.path.join(d44, fn); raw = rd(p); crlf = "\r\n" in raw; have = parse_dict(p)
        addl = [ngd[k] for k in sorted(used_keys) if k in ngd and k not in have]
        if addl:
            nl = "\r\n" if crlf else "\n"; body = raw if raw.endswith("\n") or not raw else raw + nl
            wr(p, body + nl.join(addl) + nl); step("сделано", "словарь %s: +%d ключей" % (fn, len(addl)))

print()
bad = [r for r in results if r[0] in ("НЕ НАЙДЕНО", "НЕТ ФАЙЛА", "НЕТ В NG", "ВНИМАНИЕ")]
print("Итого: %d шагов, из них требуют внимания: %d" % (len(results), len(bad)))
for st, nm in bad: print("  %-11s %s" % (st, nm))
