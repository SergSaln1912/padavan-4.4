#!/usr/bin/env python3
"""
Правки, которые потребовались при сборке padavan-4.4 (накопительный список, повторный запуск безопасен).

  python3 port-build-fixes.py <путь_к_padavan-4.4>
"""
import os, re, sys

if len(sys.argv) < 2: print(__doc__); sys.exit(1)
REPO = os.path.abspath(sys.argv[1])

def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape", newline="") as f: return f.read()
def wr(p, s):
    with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="") as f: f.write(s)

def fix(rel, name, pattern, repl, marker):
    p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    s = rd(p)
    if marker in s: print("уже есть     %s" % name); return
    new, n = re.subn(pattern, repl, s, count=1)
    if n: wr(p, new); print("сделано      %s" % name)
    else: print("НЕ НАЙДЕНО   %s (шаблон не совпал в %s)" % (name, rel))

# 1. libnetfilter_queue: configure должен видеть .pc-файлы библиотек, установленных в stage
fix("trunk/libs/libnetfilter_queue/Makefile", "libnetfilter_queue: PKG_CONFIG_LIBDIR для configure",
    r"\t\./configure \\\n",
    "\tPKG_CONFIG_LIBDIR=$(STAGEDIR)/lib/pkgconfig PKG_CONFIG_PATH=$(STAGEDIR)/lib/pkgconfig \\\n\t./configure \\\n",
    "PKG_CONFIG_LIBDIR")

# 2. web_ex.c: в 4.4 нет флага need_mtd_write — сохраняем файлы zapret во флеш прямо при изменении
fix("trunk/user/httpd/web_ex.c", "web_ex.c: сохранение файлов zapret вместо need_mtd_write",
    r"\t\t\t\t\tneed_mtd_write = 1;\n",
    '\t\t\t\t\tdoSystem("/sbin/mtd_storage.sh save");\t/* ng-port: сохранить файлы zapret во флеш */\n',
    "ng-port: сохранить файлы zapret во флеш")

# 3. zapret2: nfq2/Makefile ищет LuaJIT через pkg-config -> нужен путь к .pc-файлам в stage
fix("trunk/user/zapret/zapret2/Makefile", "zapret2: PKG_CONFIG_LIBDIR для поиска luajit",
    r"\t\$\(MAKE\) -j\$\(HOST_NCPU\) -C \$\(SRC_NAME\)\n",
    "\tPKG_CONFIG_LIBDIR=$(STAGEDIR)/lib/pkgconfig PKG_CONFIG_PATH=$(STAGEDIR)/lib/pkgconfig \\\n\t\t$(MAKE) -j$(HOST_NCPU) -C $(SRC_NAME)\n",
    "PKG_CONFIG_LIBDIR")

# ---------------------------------------------------------------- 4-6. firewall_ex.c: доводка блоков AmneziaWG
def fw_fixes():
    rel = "trunk/user/rc/firewall_ex.c"
    p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n"); changed = False

    # 4. интерфейс VPN-клиента AWG в правилах filter (первое место, где задаётся vpnc_if)
    mk = "ng-port: vpnc_if awg (filter)"
    if mk in s: print("уже есть     firewall_ex.c: vpnc_if для AWG (filter)")
    else:
        pat = re.compile(r"(\tvpnc_if = NULL;\n\tif \(i_vpnc_enable\) \{\n)(#if defined \(APP_OPENVPN\)\n\t\tif \(i_vpnc_type == 2\) \{)")
        blk = ("#if defined (APP_AMNEZIAWG)\t/* %s */\n\t\tif (i_vpnc_type == 3) {\n\t\t\tvpnc_if = IFNAME_CLIENT_WG;\n"
               "\t\t} else\n#endif\n" % mk)
        s2, n = pat.subn(lambda m: m.group(1) + blk + m.group(2), s, count=1)
        if n: s, changed = s2, True; print("сделано      firewall_ex.c: vpnc_if для AWG (filter)")
        else: print("НЕ НАЙДЕНО   firewall_ex.c: vpnc_if для AWG (filter)")

    # 5. правило списка VPN для режима доступа сервера 4: ветка получает фигурные скобки и WG-правило
    mk2 = "ng-port: vpnlist awg"
    if mk2 in s: print("уже есть     firewall_ex.c: правило vpnlist для AWG")
    else:
        pat = re.compile(r'(?P<i>\t+)else if \(i_vpns_actl == 4\)\n(?P<j>\t+)fprintf\(fp, "-A %s -o %s -j %s\\n", dtype, wan_if, IPT_CHAIN_NAME_VPN_LIST\);\n'
                         r'(?P=i)else\n(?P=j)fprintf\(fp, "-A %s -o %s -j %s\\n", dtype, lan_if, IPT_CHAIN_NAME_VPN_LIST\);\n')
        def repl(m):
            i, j = m.group("i"), m.group("j")
            return (i + "else if (i_vpns_actl == 4) {\n"
                    + j + 'fprintf(fp, "-A %s -o %s -j %s\\n", dtype, wan_if, IPT_CHAIN_NAME_VPN_LIST);\n'
                    + "#if defined (APP_AMNEZIAWG)\t/* " + mk2 + " */\n"
                    + j + "if (vpnc_if && i_vpnc_type == 3) {\n"
                    + j + '\tfprintf(fp, "-A %s -o %s -j %s\\n", dtype, vpnc_if, IPT_CHAIN_NAME_VPN_LIST);\n'
                    + j + "}\n#endif\n"
                    + i + "} else\n"
                    + j + 'fprintf(fp, "-A %s -o %s -j %s\\n", dtype, lan_if, IPT_CHAIN_NAME_VPN_LIST);\n')
        s2, n = pat.subn(repl, s, count=1)
        if n: s, changed = s2, True; print("сделано      firewall_ex.c: правило vpnlist для AWG")
        else: print("НЕ НАЙДЕНО   firewall_ex.c: правило vpnlist для AWG (ветка i_vpns_actl == 4)")

    # 6. include_masquerade в блоках AWG: в 4.4 пять параметров (is_fullcone), в padavan-ng четыре
    lines = s.split("\n"); in_awg = False; depth = 0; fixed = 0
    for idx, l in enumerate(lines):
        st = l.strip()
        if re.match(r"#\s*if\s+defined\s*\(\s*APP_AMNEZIAWG\s*\)", st) and not in_awg: in_awg, depth = True, 1; continue
        if in_awg:
            if re.match(r"#\s*if", st): depth += 1
            elif re.match(r"#\s*endif", st):
                depth -= 1
                if depth == 0: in_awg = False
            def fixcall(m):
                global_args = m.group(1)
                if global_args.count(",") == 3:
                    return "include_masquerade(%s, 0)" % global_args
                return m.group(0)
            new = re.sub(r"include_masquerade\(([^()]*)\)", fixcall, l)
            if new != l: lines[idx] = new; fixed += 1
    if fixed: s, changed = "\n".join(lines), True; print("сделано      firewall_ex.c: include_masquerade(..., 0) в блоках AWG: %d вызов(ов)" % fixed)
    else: print("уже есть     firewall_ex.c: include_masquerade в блоках AWG")

    if changed: wr(p, s.replace("\n", "\r\n") if crlf else s)
fw_fixes()

# ---------------------------------------------------------------- 7. mtd_storage.sh: файлы хранилища AmneziaWG в стиле 4.4
def awg_storage():
    rel = "trunk/user/scripts/mtd_storage.sh"
    p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "amneziawg files (ng-port)" in s: print("уже есть     mtd_storage.sh: файлы хранилища AmneziaWG"); return
    files = (("vpnc_post_script.sh", "755"), ("vpnc_remote_network.list", "644"), ("vpnc_exclude_network.list", "644"))
    blocks = []
    for name, mode in files:
        tp = os.path.join(REPO, "trunk/user/scripts/storage", name)
        if not os.path.exists(tp): print("НЕТ ШАБЛОНА  %s (ожидался в trunk/user/scripts/storage)" % name); return
        body = rd(tp).replace("\r\n", "\n")
        if not body.endswith("\n"): body += "\n"
        if "\nEOF_AWG\n" in "\n" + body: print("ОШИБКА       шаблон %s содержит строку EOF_AWG" % name); return
        blocks.append('\t\tif [ ! -f "$dir_storage/%s" ] ; then\n'
                      '\t\t\tcat > "$dir_storage/%s" <<\'EOF_AWG\'\n%sEOF_AWG\n'
                      '\t\t\tchmod %s "$dir_storage/%s"\n\t\tfi\n' % (name, name, body, mode, name))
    text = ('\t# create amneziawg files (ng-port)\n'
            '\tif [ -s /lib/modules/$(uname -r)/kernel/net/amneziawg/amneziawg.ko ] ; then\n'
            + "".join(blocks) + '\tfi\n')
    # метка блока (по ней проверяется идемпотентность)
    text = text.replace("# create amneziawg files (ng-port)", "# amneziawg files (ng-port)", 1)
    anchor = "\t# create zapret files\n"
    if anchor in s: s = s.replace(anchor, text + anchor, 1)
    else:
        m = re.search(r"^\}\n\ncase \"\$1\" in\n", s, re.M)
        if not m: print("НЕ НАЙДЕНО   mtd_storage.sh: конец func_fill"); return
        s = s[:m.start()] + text + s[m.start():]
    wr(p, s.replace("\n", "\r\n") if crlf else s)
    print("сделано      mtd_storage.sh: файлы хранилища AmneziaWG (vpnc_post_script.sh, списки сетей)")
awg_storage()

# ---------------------------------------------------------------- 8. fullcone NAT не поддерживается в 4.4
# iptables-restore: unknown option "--mode" (MASQUERADE --mode fullcone), ip6tables: нет цели FULLCONENAT.
# Из-за этого весь пакет правил NAT отвергался и клиенты не получали интернет.
def nofullcone():
    rel = "trunk/user/rc/firewall_ex.c"
    p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n"); changed = False
    m1 = "ng-port: no fullcone"
    if m1 in s: print("уже есть     firewall_ex.c: fullcone в include_masquerade отключён")
    elif "\tif (is_fullcone) {\n" in s:
        s = s.replace("\tif (is_fullcone) {\n", "\tif (0 /* ng-port: no fullcone in 4.4 */ && is_fullcone) {\n", 1)
        changed = True; print("сделано      firewall_ex.c: fullcone в include_masquerade отключён")
    else: print("НЕ НАЙДЕНО   firewall_ex.c: if (is_fullcone) {")
    line = '\tfprintf(fp, "-A POSTROUTING -s fc00:101:101::1/64 -j FULLCONENAT\\n");\n'
    m2 = "ng-port: no FULLCONENAT"
    if m2 in s: print("уже есть     firewall_ex.c: FULLCONENAT для IPv6 убран")
    elif line in s:
        s = s.replace(line, "\t/* ng-port: no FULLCONENAT in 4.4 */\n", 1)
        changed = True; print("сделано      firewall_ex.c: FULLCONENAT для IPv6 убран")
    else: print("НЕ НАЙДЕНО   firewall_ex.c: строка FULLCONENAT (IPv6)")
    if changed: wr(p, s.replace("\n", "\r\n") if crlf else s)
nofullcone()

# nf_nat_type по умолчанию = 2 (обычный NAT)
fix("trunk/user/shared/defaults.c", "defaults.c: nf_nat_type по умолчанию 2",
    r'\{\s*"nf_nat_type"\s*,\s*"1"\s*\}', '{ "nf_nat_type", "2" }', '"nf_nat_type", "2"')

# ---------------------------------------------------------------- 9. меню VPN Server/Client только с AmneziaWG
# found_app_vpnsvr/found_app_vpncli в web_ex.c зависят только от APP_OPENVPN -> без OpenVPN пункты меню скрыты.
def vpn_menu():
    rel = "trunk/user/httpd/web_ex.c"
    p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    s = rd(p)
    pat = re.compile(r"#if (defined ?\([A-Z_0-9]+\)(?: \|\| defined ?\([A-Z_0-9]+\))*)(\r?\n\s*int found_app_vpn(?:svr|cli) = 1;)")
    def sub(m):
        if "APP_AMNEZIAWG" in m.group(1): return m.group(0)
        return "#if %s || defined (APP_AMNEZIAWG)%s" % (m.group(1), m.group(2))
    new, n = pat.subn(sub, s)
    if new != s: wr(p, new); print("сделано      web_ex.c: пункты меню VPN Server/Client для AmneziaWG")
    elif n: print("уже есть     web_ex.c: меню VPN для AmneziaWG")
    else: print("НЕ НАЙДЕНО   web_ex.c: блоки found_app_vpnsvr/found_app_vpncli")
vpn_menu()

# ---------------------------------------------------------------- 10. www/Makefile: страницы VPN не удалять при AmneziaWG
def www_vpn():
    rel = "trunk/user/www/Makefile"
    p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "ng-port: vpn pages" in s: print("уже есть     www/Makefile: страницы VPN для AmneziaWG"); return
    a = ("ifneq ($(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_SERVER),y)\n\trm -f $(INSTALLDIR)/www/vpnsrv.asp\nendif\n")
    b = ("ifneq ($(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT),y)\n\trm -f $(INSTALLDIR)/www/vpn_clients.asp\n\trm -f $(INSTALLDIR)/www/vpncli.asp\nendif\n")
    if a not in s or b not in s: print("НЕ НАЙДЕНО   www/Makefile: блоки удаления vpnsrv.asp/vpncli.asp"); return
    s = s.replace(a, "# ng-port: vpn pages\nifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_SERVER) $(CONFIG_FIRMWARE_INCLUDE_AMNEZIAWG)))\n\trm -f $(INSTALLDIR)/www/vpnsrv.asp\nendif\n", 1)
    s = s.replace(b, "ifneq ($(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT),y)\n\trm -f $(INSTALLDIR)/www/vpn_clients.asp\nendif\n"
                     "ifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT) $(CONFIG_FIRMWARE_INCLUDE_AMNEZIAWG)))\n\trm -f $(INSTALLDIR)/www/vpncli.asp\nendif\n", 1)
    wr(p, s.replace("\n", "\r\n") if crlf else s)
    print("сделано      www/Makefile: vpnsrv.asp и vpncli.asp остаются при AmneziaWG")
www_vpn()

# ---------------------------------------------------------------- 11. ipset list:set
# wgc.sh/wgs.sh и zapret создают наборы vpn.remote.list/vpn.exclude.list/nozapret.list типом list:set;
# в 4.4 модуль ip_set_list_set не загружался -> "Set ... doesn't exist", firewall rules update failed.
def ipset_list_set():
    rel = "trunk/user/rc/rc.c"
    p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p)
    if 'module_smart_load("ip_set_list_set"' in raw: print("уже есть     rc.c: загрузка ip_set_list_set"); return
    m = re.search(r'([ \t]*)module_smart_load\("ip_set_hash_net", NULL\);(\r?\n)', raw)
    if not m: print("НЕ НАЙДЕНО   rc.c: module_smart_load(ip_set_hash_net)"); return
    ins = '%smodule_smart_load("ip_set_list_set", NULL);%s' % (m.group(1), m.group(2))
    wr(p, raw[:m.end()] + ins + raw[m.end():])
    print("сделано      rc.c: загрузка ip_set_list_set")
ipset_list_set()

# ---------------------------------------------------------------- 12. страницы VPN: нет ej-функции get_ipset_list_hook в 4.4
# Без службы IPSet в httpd 4.4 нет get_ipset_list_hook(); необработанный тег <% ... %> попадает в JavaScript
# ("Unexpected token '<'"), весь скрипт страницы не разбирается (initial/change_vpnc_enabled is not defined).
def no_ipset_hook():
    for name in ("vpncli.asp", "vpnsrv.asp"):
        rel = "trunk/user/www/n56u_ribbon_fixed/" + name
        p = os.path.join(REPO, rel)
        if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); continue
        s = rd(p)
        pat = re.compile(r"\[\s*<%\s*get_ipset_list_hook\(\);\s*%>\s*\]")
        new, n = pat.subn("[]", s)
        if n: wr(p, new); print("сделано      %s: get_ipset_list_hook() -> []" % name)
        else: print("уже есть     %s: get_ipset_list_hook() не используется" % name)
no_ipset_hook()

# 13: Advanced_Services_Zapret.asp: нет хуков get_ipset_list_hook и net_iface_list
def zapret_hooks():
    import glob
    # 13a: get_ipset_list_hook -> [] во всех страницах исходников
    pat = re.compile(r"\[\s*<%\s*get_ipset_list_hook\(\);\s*%>\s*\]")
    cnt = 0
    for p in glob.glob(os.path.join(REPO, "trunk/user/www/*/*.asp")):
        s = rd(p); new, n = pat.subn("[]", s)
        if n: wr(p, new); cnt += 1; print("сделано      %s: get_ipset_list_hook() -> []" % os.path.relpath(p, REPO))
    if not cnt: print("уже есть     get_ipset_list_hook() нигде не используется")
    # 13b: ej_net_iface_list в httpd/web_ex.c
    rel = "trunk/user/httpd/web_ex.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    s = rd(p)
    if "ej_net_iface_list" in s: print("уже есть     web_ex.c: ej_net_iface_list"); return
    func = ('/* ng-port: net_iface_list */\n'
            'static int ej_net_iface_list(int eid, webs_t wp, int argc, char **argv)\n'
            '{\n'
            '\tDIR *d = opendir("/sys/class/net");\n'
            '\tstruct dirent *e;\n'
            '\tint first = 1;\n'
            '\tif (!d) return 0;\n'
            '\twhile ((e = readdir(d)) != NULL) {\n'
            '\t\tif (e->d_name[0] == \'.\' || !strcmp(e->d_name, "lo")) continue;\n'
            '\t\twebsWrite(wp, "%s\\"%s\\"", first ? "" : ",", e->d_name);\n'
            '\t\tfirst = 0;\n'
            '\t}\n'
            '\tclosedir(d);\n'
            '\treturn 0;\n'
            '}\n\n')
    m = re.search(r"^(static\s+)?int\s+ej_get_static_client\s*\(", s, re.M) or re.search(r"^struct\s+ej_handler\s+ej_handlers\s*\[", s, re.M)
    if not m: print("НЕ НАЙДЕНО   web_ex.c: место для функции"); return
    s = s[:m.start()] + func + s[m.start():]
    s, n = re.subn(r'(\n[ \t]*\{ "get_static_client",)', r'\n\t{ "net_iface_list", ej_net_iface_list},\1', s, count=1)
    if not n: print("НЕ НАЙДЕНО   web_ex.c: таблица обработчиков"); return
    if "<dirent.h>" not in s:
        s = re.sub(r"(^#include[^\n]*\n)", r"\1#include <dirent.h>\n", s, count=1, flags=re.M)
    wr(p, s); print("сделано      web_ex.c: добавлен ej_net_iface_list")
zapret_hooks()

# ---------------------------------------------------------------- 14. AmneziaWG: RandomTrailers по умолчанию включён
# На 4.4 при randomtrailers=0 сервер отвечает только на первые пакеты (данные и повторные рукопожатия не проходят).
# Профили AWG 3.1 (в т.ч. Cloudflare WARP) используют RandomTrailers = on, поэтому значение по умолчанию — 1.
def awg_randomtrailers():
    rel = "trunk/user/shared/defaults.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    s = rd(p)
    pat = re.compile(r'(\{\s*"vpnc_awg_randomtrailers"\s*,\s*)"0"')
    if pat.search(s):
        wr(p, pat.sub(r'\1"1"', s, count=1)); print("сделано      defaults.c: vpnc_awg_randomtrailers = 1")
    elif re.search(r'"vpnc_awg_randomtrailers"\s*,\s*"1"', s): print("уже есть     defaults.c: vpnc_awg_randomtrailers = 1")
    else: print("НЕ НАЙДЕНО   defaults.c: vpnc_awg_randomtrailers")
awg_randomtrailers()

# ---------------------------------------------------------------- 15. утилита nvram: буфер значения 1024 -> NVRAM_MAX_VALUE_LEN
# В 4.4 user/nvram/nvram.c читает значение в char buf[1024]: `nvram get/show` режет значения до 1023 байт.
# wgc.sh читает I1 (2507 символов) через `nvram get` -> модуль получал обрезанный I1, сервер WARP не отвечал.
def nvram_buf():
    rel = "trunk/user/nvram/nvram.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    s = rd(p)
    n = len(re.findall(r"char\s+buf\s*\[\s*1024\s*\]", s))
    if n == 0:
        print("уже есть     nvram.c: буфер значения не 1024"); return
    s = re.sub(r"char(\s+)buf(\s*)\[\s*1024\s*\]", r"char\1buf\2[NVRAM_MAX_VALUE_LEN]", s)
    if "NVRAM_MAX_VALUE_LEN" not in s.split("char", 1)[0] and not re.search(r"#\s*define\s+NVRAM_MAX_VALUE_LEN", s):
        guard = "#ifndef NVRAM_MAX_VALUE_LEN\n#define NVRAM_MAX_VALUE_LEN 4096\n#endif\n"
        incs = list(re.finditer(r"^#include[^\n]*\n", s, re.M))
        pos = incs[-1].end() if incs else 0
        s = s[:pos] + guard + s[pos:]
    wr(p, s); print("сделано      nvram.c: char buf[1024] -> NVRAM_MAX_VALUE_LEN (%d мест)" % n)
nvram_buf()

# ---------------------------------------------------------------- 16. команда update_resolvconf (нужна wgc.sh)
# wgc.sh вызывает `update_resolvconf`, чтобы подставить DNS туннеля. В 4.4 её нет (rc.c и Makefile):
# "wgc.sh: line 666: update_resolvconf: not found" -> DNS клиентов через туннель не работает.
def update_resolvconf_cmd():
    rel = "trunk/user/rc/rc.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel)
    else:
        raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
        if 'strcmp(base, "update_resolvconf")' in s:
            print("уже есть     rc.c: update_resolvconf")
        else:
            m = re.search(r'^([ \t]*)else if \(!strcmp\(base, "ejusb"\)\) \{', s, re.M)
            if not m: print("НЕ НАЙДЕНО   rc.c: место для update_resolvconf (ejusb)")
            else:
                ind = m.group(1)
                block = (ind + 'else if (!strcmp(base, "update_resolvconf")) {\n'
                         + ind + '\tupdate_resolvconf(0, 0);\n' + ind + '}\n')
                s = s[:m.start()] + block + s[m.start():]
                wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      rc.c: добавлен обработчик update_resolvconf")
    # Ссылка должна ставиться БЕЗУСЛОВНО: блок с ejusb собирается только при CONFIG_USB_SUPPORT,
    # а в RM2100 USB выключен -> команды update_resolvconf в образе не было. Старую (ошибочную) строку убираем.
    rel = "trunk/user/rc/Makefile"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    link = re.compile(r"^[ \t]*cd \$\(INSTALLDIR\)/sbin && ln -sf rc update_resolvconf[ \t]*\n", re.M)
    anchor = re.search(r"^([ \t]*)cd \$\(INSTALLDIR\)/sbin && ln -sf rc restart_dns[ \t]*\n", s, re.M)
    if not anchor: print("НЕ НАЙДЕНО   rc/Makefile: место для ссылки (restart_dns)"); return
    nxt = s[anchor.end():anchor.end()+80]
    if len(link.findall(s)) == 1 and nxt.lstrip().startswith("cd $(INSTALLDIR)/sbin && ln -sf rc update_resolvconf"):
        print("уже есть     rc/Makefile: ссылка update_resolvconf (безусловная)"); return
    s = link.sub("", s)
    anchor = re.search(r"^([ \t]*)cd \$\(INSTALLDIR\)/sbin && ln -sf rc restart_dns[ \t]*\n", s, re.M)
    s = s[:anchor.end()] + anchor.group(1) + "cd $(INSTALLDIR)/sbin && ln -sf rc update_resolvconf\n" + s[anchor.end():]
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      rc/Makefile: ссылка update_resolvconf (безусловно, после restart_dns)")
update_resolvconf_cmd()

# ---------------------------------------------------------------- 17. httpd: отдача *.json (amneziawg.json)
# Страница VPN-клиента читает /amneziawg.json (loadJSON). В 4.4 в mime_handlers нет шаблона **.json -> 404,
# импорт параметров AWG (I1, Jmin, Jmax, DisableCookies, ...) из .conf молча не работает.
def httpd_json():
    rel = "trunk/user/httpd/web_ex.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if re.search(r'\{\s*"\*\*\.json"', s): print("уже есть     web_ex.c: **.json в mime_handlers"); return
    m = re.search(r'^([ \t]*)\{\s*"\*\*\.(?:js|css|gif)",\s*"[^"]*",\s*([A-Za-z_0-9]+),\s*(NULL|[A-Za-z_0-9]+),\s*([A-Za-z_0-9]+),\s*(\d+)\s*\},[^\n]*\n', s, re.M)
    if not m:
        m2 = re.search(r'struct\s+mime_handler\s+mime_handlers\s*\[\s*\]\s*=\s*\{\n', s)
        if not m2: print("НЕ НАЙДЕНО   web_ex.c: таблица mime_handlers"); return
        ind, cache, cb, handler, auth = "\t", "no_cache_IE", "NULL", "do_file", "0"
        pos = m2.end()
    else:
        ind, cache, cb, handler, auth = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5); pos = m.end()
    line = '%s{ "**.json", "application/json", %s, %s, %s, %s },\n' % (ind, cache, cb, handler, auth)
    s = s[:pos] + line + s[pos:]
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      web_ex.c: добавлен **.json (application/json)")
httpd_json()

# ---------------------------------------------------------------- 18. значения по умолчанию: LAN 192.168.1.1, язык EN
def lan_lang_defaults():
    import glob
    pat = re.compile(r'(#\s*define\s+DEF_LAN_(?:ADDR|DHCP_BEG|DHCP_END)\s+")192\.168\.2\.(\d+)(")')
    done = 0; seen = 0
    for base in ("trunk/user/shared", "trunk/user/rc", "trunk/user/httpd"):
        for root, dirs, files in os.walk(os.path.join(REPO, base)):
            for fn in files:
                if not fn.endswith((".h", ".c", ".mk")): continue
                p = os.path.join(root, fn)
                try: s = rd(p)
                except Exception: continue
                if "DEF_LAN_" not in s: continue
                new, n = pat.subn(r"\g<1>192.168.1.\2\3", s)
                if n: wr(p, new); done += n; print("сделано      %s: адреса DEF_LAN_* -> 192.168.1.x (%d)" % (os.path.relpath(p, REPO), n))
                elif re.search(r'DEF_LAN_(?:ADDR|DHCP_BEG|DHCP_END)\s+"192\.168\.1\.', s): seen += 1
    if not done:
        print("уже есть     DEF_LAN_*: 192.168.1.x" if seen else "НЕ НАЙДЕНО   определения DEF_LAN_ADDR/DEF_LAN_DHCP_*")
    rel = "trunk/user/shared/defaults.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    s = rd(p)
    m = re.search(r'(\{\s*"preferred_lang"\s*,\s*)"([A-Z]*)"', s)
    if not m: print("НЕ НАЙДЕНО   defaults.c: preferred_lang"); return
    if m.group(2) == "EN": print("уже есть     defaults.c: preferred_lang = EN"); return
    wr(p, s[:m.start()] + m.group(1) + '"EN"' + s[m.end():]); print("сделано      defaults.c: preferred_lang %s -> EN" % (m.group(2) or "(пусто)"))
lan_lang_defaults()

# ---------------------------------------------------------------- 19. wgc.sh: rp_filter=0 для wg0 и тихие sysctl
# Строгий rp_filter на wg0 отбрасывает ответы из туннеля для клиентов LAN (маршрут обратно по fwmark идёт через main -> eth3).
# Интерфейс wg0 пересоздаётся при каждом запуске/перезапуске клиента, поэтому значение надо ставить в wgc.sh.
def wgc_rpfilter():
    rel = "trunk/user/wireguard/wgc.sh"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n"); changed = False
    if "ng-port: rp_filter" in s:
        print("уже есть     wgc.sh: rp_filter=0")
    else:
        m = re.search(r'^([ \t]*)ip link set dev \$IF_NAME mtu \$IF_MTU[ \t]*\n', s, re.M)
        if not m: print("НЕ НАЙДЕНО   wgc.sh: ip link set dev $IF_NAME mtu (место для rp_filter)")
        else:
            ind = m.group(1)
            add = (ind + "# ng-port: rp_filter=0 (ответы из туннеля для клиентов LAN, иначе отбрасываются)\n"
                   + ind + "echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter 2>/dev/null\n"
                   + ind + "echo 0 > /proc/sys/net/ipv4/conf/$IF_NAME/rp_filter 2>/dev/null\n")
            s = s[:m.end()] + add + s[m.end():]; changed = True; print("сделано      wgc.sh: rp_filter=0 для all и $IF_NAME")
    # тихие sysctl: в этом ядре нет ключей src_valid_mark / vm.drop_caches
    def quiet(m):
        line = m.group(0)
        return line if "2>/dev/null" in line else line.rstrip() + " 2>/dev/null"
    s2 = re.sub(r'^[ \t]*sysctl -q net\.ipv4\.conf\.all\.src_valid_mark=1[^\n]*$', quiet, s, flags=re.M)
    s2 = re.sub(r'sysctl -q vm\.drop_caches=3(?![^\n]*2>/dev/null)', 'sysctl -q vm.drop_caches=3 2>/dev/null', s2)
    if s2 != s: s = s2; changed = True; print("сделано      wgc.sh: sysctl src_valid_mark/drop_caches без ошибок")
    if changed: wr(p, s.replace("\n", "\r\n") if crlf else s)
wgc_rpfilter()

# ---------------------------------------------------------------- 20. wgc.sh: DNS роутера через туннель
# Без этого dnsmasq спрашивает внешние DNS (77.88.8.8, 8.8.8.8, ...) мимо туннеля, провайдер портит ответы
# для заблокированных и служебных доменов -> ТВ/приставки (берут DNS у роутера) пишут "нет интернета".
def wgc_dns_routes():
    rel = "trunk/user/wireguard/wgc.sh"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "ng-port: dns-routes v2" in s: print("уже есть     wgc.sh: маршруты DNS через туннель (v2)"); return
    s = re.sub(r"[ \t]*# ng-port: DNS через туннель \(внешние DNS из resolv\.conf идут в \$IF_NAME\)\n"
               r"(?:.*\n){0,6}?[ \t]*killall -HUP dnsmasq 2>/dev/null\n", "", s)
    func = ("# ng-port: dns-routes v2\n"
            "# Внешние DNS из /etc/resolv.conf (статические WAN, DNS туннеля) идут через интерфейс туннеля:\n"
            "# иначе провайдер портит ответы для заблокированных и служебных доменов (ТВ, приставки).\n"
            "ng_dns_routes()\n{\n"
            "    [ \"$IF_NAME\" ] || return\n"
            "    for _s in $(grep '^nameserver' /etc/resolv.conf | awk '{print $2}'); do\n"
            "        case \"$_s\" in 127.*|10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*|*:*) continue ;; esac\n"
            "        ip route replace $_s/32 dev $IF_NAME 2>/dev/null\n"
            "    done\n"
            "}\n\n")
    m = re.search(r'^wg_setdns\(\)\n', s, re.M)
    if not m: print("НЕ НАЙДЕНО   wgc.sh: wg_setdns()"); return
    s = s[:m.start()] + func + s[m.start():]
    m = re.search(r'^([ \t]*)update_resolvconf[ \t]*\n', s, re.M)
    if m: s = s[:m.end()] + m.group(1) + "ng_dns_routes\n" + m.group(1) + "killall -HUP dnsmasq 2>/dev/null\n" + s[m.end():]
    m = re.search(r'^([ \t]*)wg_setdns[ \t]*\n', s, re.M)
    if m: s = s[:m.end()] + m.group(1) + "ng_dns_routes\n" + s[m.end():]
    m = re.search(r'^([ \t]*)connect_wg reconnect[ \t]*\n', s, re.M)
    if m: s = s[:m.start()] + m.group(1) + "ng_dns_routes\n" + s[m.start():]
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      wgc.sh: ng_dns_routes (старт и watchdog)")
wgc_dns_routes()

# ---------------------------------------------------------------- 25. wgc.sh: DNS туннеля поверх DNS провайдера
# Загрузка и подъём туннеля идут с DNS провайдера/WAN (resolv.conf от WAN). Когда туннель поднят, wgc.sh
# подставляет DNS туннеля из профиля (адреса в прошивку не зашиты; нет DNS в профиле -> ничего не меняется) и только их (vpnc_pdns=2),
# ng_dns_routes направляет их в туннель. При остановке клиента DNS возвращаются к WAN (провайдера).
def wgc_tunnel_dns():
    # По умолчанию ВЫКЛЮЧЕНО (решение пользователя: пока ничего не менять). Включить: NG_TUNNEL_DNS=1 python3 port-build-fixes.py ...
    if os.environ.get("NG_TUNNEL_DNS") != "1":
        print("пропущено    wgc.sh: DNS туннеля поверх DNS провайдера (правило 25 выключено; NG_TUNNEL_DNS=1 включает)"); return
    rel = "trunk/user/wireguard/wgc.sh"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "ng-port: tunnel-dns" in s: print("уже есть     wgc.sh: DNS туннеля поверх DNS провайдера"); return
    m = re.search(r'^wg_setdns\(\)\n\{\n.*?^\}\n', s, re.M | re.S)
    if not m: print("НЕ НАЙДЕНО   wgc.sh: wg_setdns()"); return
    body = ('wg_setdns()\n{\n'
            '    # ng-port: tunnel-dns\n'
            '    [ "$IF_DNS" ] || return\n'
            '    _dns="$IF_DNS"\n\n'
            '    nvram set vpnc_pdns=2\n'
            '    nvram set vpnc_dns_t="$_dns"\n'
            '    update_resolvconf\n'
            '    ng_dns_routes\n'
            '    killall -HUP dnsmasq 2>/dev/null\n}\n')
    s = s[:m.start()] + body + s[m.end():]
    m = re.search(r'^stop_wg\(\)\n\{\n(?:.*\n)*?([ \t]*)stop_fw\n', s, re.M)
    if not m: print("НЕ НАЙДЕНО   wgc.sh: stop_wg()/stop_fw"); return
    ind = m.group(1)
    s = s[:m.end()] + (ind + "# ng-port: tunnel-dns (вернуть DNS провайдера)\n" + ind + 'nvram set vpnc_dns_t=""\n'
                       + ind + "update_resolvconf\n") + s[m.end():]
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      wgc.sh: DNS туннеля при старте, DNS провайдера при остановке")
wgc_tunnel_dns()

# ---------------------------------------------------------------- 26. HNAT: убрать сообщение "mtk_pong_hqos_handler:drop" из лога ядра
# Пакеты из Wi-Fi, которые не удалось отдать аппаратному ускорению, сбрасываются и раньше попадали в лог (printk_ratelimited).
# Поведение (NF_DROP) не меняется, отключается только вывод. Возврат: удалить маркер #if 0 / #endif вокруг printk.
def hnat_quiet_pong():
    found = False
    for rel in ("trunk/linux-4.4.x/drivers/net/ethernet/mediatek/mtk_hnat/hnat_nf_hook.c",
                "trunk/linux-4.4.x/drivers/net/ethernet/raeth/mtk_hnat/hnat_nf_hook.c"):
        p = os.path.join(REPO, rel)
        if not os.path.exists(p): continue
        found = True
        raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
        if "ng-port: pong drop log off" in s: print("уже есть     %s: сообщение pong drop отключено" % rel); continue
        a = s.find("mtk_pong_hqos_handler(void *priv")
        if a < 0: print("НЕ НАЙДЕНО   %s: mtk_pong_hqos_handler" % rel); continue
        m = re.compile(r"^drop:\n([ \t]*)(printk_ratelimited\(KERN_WARNING\n(?:.*\n)*?.*skb_hnat_alg\(skb\)\);\n)", re.M).search(s, a)
        if not m or "return NF_DROP" not in s[m.end():m.end()+40]:
            print("НЕ НАЙДЕНО   %s: printk в drop: pong" % rel); continue
        new = "drop:\n#if 0 /* ng-port: pong drop log off */\n" + m.group(1) + m.group(2) + "#endif\n"
        s = s[:m.start()] + new + s[m.end():]
        wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      %s: сообщение pong drop отключено" % rel)
    if not found: print("НЕТ ФАЙЛА    hnat_nf_hook.c")
hnat_quiet_pong()

# ---------------------------------------------------------------- 27. DoH/DoT/DNSCrypt доступны на выбор для всех плат
# В профилях остальных плат добавляются флаги FIRMWARE_INCLUDE_DNSCRYPT/STUBBY/DOH со значением n (выключено),
# существующие значения не трогаются. Включить для платы: заменить n на y в trunk/configs/templates/<ПЛАТА>.config.
# Остальные флаги (Shadowsocks, OpenVPN, язык) в других платах уже есть и остаются как были.
def dns_flags_all_boards():
    d = os.path.join(REPO, "trunk/configs/templates")
    if not os.path.isdir(d): print("НЕТ КАТАЛОГА trunk/configs/templates"); return
    added = 0; boards = 0
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".config") or fn == "RM2100.config": continue
        p = os.path.join(d, fn); raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
        miss = [f for f in ("DNSCRYPT", "STUBBY", "DOH")
                if not re.search(r'^[ \t]*#?[ \t]*CONFIG_FIRMWARE_INCLUDE_%s[= ]' % f, s, re.M)]
        if not miss: continue
        add = "".join("CONFIG_FIRMWARE_INCLUDE_%s=n\n" % f for f in miss)
        m = re.search(r'^[ \t]*#?[ \t]*CONFIG_FIRMWARE_INCLUDE_OPENVPN=.*\n', s, re.M)
        if m: s = s[:m.end()] + add + s[m.end():]
        else: s = s.rstrip("\n") + "\n" + add
        wr(p, s.replace("\n", "\r\n") if crlf else s); added += len(miss); boards += 1
    print("сделано      профили плат: флаги DNSCRYPT/STUBBY/DOH=n добавлены в %d файлов (%d строк)" % (boards, added) if boards
          else "уже есть     профили плат: флаги DNSCRYPT/STUBBY/DOH")
dns_flags_all_boards()

# ---------------------------------------------------------------- 28. autostart.sh: сообщения журнала по-английски
# В системном журнале строки автозапуска были на китайском (自动启动 ...). Переводятся только тексты logger, логика не меняется.
def autostart_english():
    rel = "trunk/user/scripts/autostart.sh"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    tr = [
        ('logger -t "防止 DNSmasq 启动失败，创建/tmp/dnsmasq.dom/"', 'logger -t "autostart" "Creating /tmp/dnsmasq.dom/ to prevent dnsmasq start failure"'),
        ("正在检查路由是否已连接互联网...", "Checking whether the router is connected to the Internet..."),
        ("正在启动 SQM QOS...", "Starting SQM QoS..."),
        ("正在启动 Adbyby plus...", "Starting Adbyby plus..."),
        ("正在启动 adguardhome...", "Starting AdGuard Home..."),
        ("正在启动科学上网...", "Starting proxy services..."),
        ("正在启动 SmartDNS...", "Starting SmartDNS..."),
        ("正在启动阿里ddns...", "Starting Aliyun DDNS..."),
        ("正在启动 ddnsto...", "Starting ddnsto..."),
        ("正在启动阿里云盘...", "Starting Aliyun Drive..."),
        ("正在启动 zerotier...", "Starting ZeroTier..."),
        ("正在启动 wireguard...", "Starting WireGuard..."),
        ("正在启动frp client...", "Starting FRP client..."),
    ]
    n = 0
    for a, b in tr:
        if a in s: s = s.replace(a, b); n += 1
    s = s.replace('logger -t "自动启动"', 'logger -t "autostart"')
    left = re.findall(r'^[^#\n]*logger[^\n]*[\u4e00-\u9fff][^\n]*$', s, re.M)
    if n == 0 and "自动启动" not in raw: print("уже есть     autostart.sh: сообщения на английском"); return
    wr(p, s.replace("\n", "\r\n") if crlf else s)
    print("сделано      autostart.sh: сообщения logger по-английски (%d строк)" % n + ("; осталось с китайским: %d" % len(left) if left else ""))
autostart_english()

# ---------------------------------------------------------------- 29. STAGEDIR для CMake берётся из окружения make, а не из оболочки
# vendors/cmake/cross-mipsel-linux.cmake читает $ENV{STAGEDIR}, но trunk/Makefile его не экспортировал. Если в оболочке
# остался STAGEDIR от сборки padavan-ng, CMake брал OpenSSL 3 из padavan-ng/trunk/stage:
# https_dns_proxy и stubby требовали libssl.so.3 (в 4.4 только OpenSSL 1.1.1w) и не запускались.
def export_stagedir():
    rel = "trunk/Makefile"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if re.search(r"^export\b[^\n]*\bSTAGEDIR\b", s, re.M): print("уже есть     trunk/Makefile: export STAGEDIR"); return
    m = re.search(r"^(export CONFIG_CMAKE_TOOLCHAIN_FILE[^\n]*)$", s, re.M)
    if not m: print("НЕ НАЙДЕНО   trunk/Makefile: строка export CONFIG_CMAKE_TOOLCHAIN_FILE"); return
    s = s[:m.end()] + "\nexport STAGEDIR # ng-port: CMake читает $ENV{STAGEDIR}" + s[m.end():]
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      trunk/Makefile: export STAGEDIR")
export_stagedir()

# ---------------------------------------------------------------- 30. mtd_write: перезагрузка после записи прошивки напрямую через ядро
# После записи раздела firmware (в нём же squashfs rootfs) do_reboot() вызывал system("/sbin/reboot"): запускается /bin/sh и rc
# с уже перезаписанного rootfs, процесс зависает (в журнале SQUASHFS error), до вызова reboot(2) дело не доходит -> роутер
# не перезагружается после обновления из веб-интерфейса. Для команды write сразу sync() и reboot(2).
def mtd_hard_reboot():
    rel = "trunk/user/mtd_write/mtd.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "ng-port: hard_reboot" in s: print("уже есть     mtd.c: прямая перезагрузка после write"); return
    a = "static void do_reboot(void)\n{"
    old = '\t/* try regular reboot method first */\n\tsystem("/sbin/reboot");\n\tsleep(2);\n'
    if a not in s or old not in s: print("НЕ НАЙДЕНО   mtd.c: do_reboot"); return
    new = ('\t/* ng-port: hard_reboot (после записи firmware rootfs уже перезаписан, /sbin/reboot и /bin/sh недоступны) */\n'
           '\tif (!hard_reboot) {\n\t\t/* try regular reboot method first */\n\t\tsystem("/sbin/reboot");\n\t\tsleep(2);\n\t} else {\n\t\tsync();\n\t}\n')
    s = s.replace(old, new, 1)
    s = s.replace(a, "static int hard_reboot = 0;\n\n" + a, 1)
    case = "\t\tcase CMD_WRITE:\n\t\t\tif (!unlocked)\n\t\t\t\tmtd_unlock(device);\n\t\t\tmtd_write(imagefd, device, fis_layout, part_offset);\n"
    if case not in s: print("НЕ НАЙДЕНО   mtd.c: case CMD_WRITE"); return
    s = s.replace(case, case + "\t\t\thard_reboot = 1;\n", 1)
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      mtd.c: после write перезагрузка через reboot(2) без system()")
mtd_hard_reboot()

# ---------------------------------------------------------------- 31. Версия прошивки: вместо даты сборки короткий хеш git (как в образах padavan-ng)
# trunk/versions.inc: FIRMWARE_BUILDS_REV=$(shell git rev-parse --short=7 HEAD) -> "4.4.198.9-100_a1b2c3d" (до 8 символов; без git суффикс пропадает).
# Версия вшивается флагом -DFWREVSTR в user/rc/common_ex.c, а make не отслеживает смену флагов: чтобы после нового коммита
# хеш обновлялся, common_ex.o в rc/Makefile пересобирается при каждой сборке (один небольшой файл).
def version_rev_git():
    rel = "trunk/versions.inc"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel)
    else:
        raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
        # --short=7: в большом репозитории git сам берёт 9 знаков, а common_ex.c принимает не больше 8 (иначе суффикса нет совсем)
        if "git rev-parse --short=7" in s: print("уже есть     versions.inc: BUILDS_REV = git rev-parse --short=7")
        else:
            n, c = re.subn(r"^FIRMWARE_BUILDS_REV=.*$", "FIRMWARE_BUILDS_REV=$(shell git rev-parse --short=7 HEAD 2>/dev/null)", s, count=1, flags=re.M)
            if c: wr(p, n.replace("\n", "\r\n") if crlf else n); print("сделано      versions.inc: FIRMWARE_BUILDS_REV = хеш git")
            else: print("НЕ НАЙДЕНО   versions.inc: FIRMWARE_BUILDS_REV")
    rel = "trunk/user/rc/Makefile"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "ng-port: force common_ex" in s: print("уже есть     rc/Makefile: пересборка common_ex.o"); return
    # после цели all (иначе первой целью по умолчанию станет force_common_ex): перед "c.o:"
    m = re.search(r"^c\.o:\n", s, re.M)
    if not m or not re.search(r"^all:", s[:m.start()], re.M): print("НЕ НАЙДЕНО   rc/Makefile: места после цели all (c.o:)"); return
    s = s[:m.start()] + "# ng-port: force common_ex (версия прошивки в common_ex.c)\n.PHONY: force_common_ex\nforce_common_ex:\ncommon_ex.o: force_common_ex\n\n" + s[m.start():]
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      rc/Makefile: common_ex.o пересобирается при каждой сборке")
version_rev_git()

# ---------------------------------------------------------------- 32. Имя образа содержит хеш версии: RM2100_4.4.198.9-100_<хеш>.trx
# vendors/Ralink/Makefile: IMAGE = ..._$(FIRMWARE_BUILDS_VER).trx -> ..._$(FIRMWARE_BUILDS_VER)_$(FIRMWARE_BUILDS_REV).trx
# (как в строке версии на роутере; без git суффикс не добавляется).
def image_name_rev():
    rel = "trunk/vendors/Ralink/Makefile"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "$(FIRMWARE_BUILDS_REV)" in s: print("уже есть     Ralink/Makefile: хеш в имени образа"); return
    old = "-$(FIRMWARE_BUILDS_VER).trx"
    if old not in s: print("НЕ НАЙДЕНО   Ralink/Makefile: имя образа (IMAGE)"); return
    s = s.replace(old, "-$(FIRMWARE_BUILDS_VER)$(if $(FIRMWARE_BUILDS_REV),_$(FIRMWARE_BUILDS_REV)).trx", 1)
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      Ralink/Makefile: имя образа с хешем версии")
image_name_rev()

# ---------------------------------------------------------------- вспомогательная: значение CONFIG_* в профиле RM2100.config
def set_cfg(name, value, note=None):
    rel = "trunk/configs/templates/RM2100.config"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    line = "CONFIG_%s=%s" % (name, value)
    m = re.search(r'^[ \t]*#?[ \t]*CONFIG_%s=.*$' % re.escape(name), s, re.M)
    if m:
        if m.group(0).strip() == line: print("уже есть     RM2100.config: %s" % line); return
        s = s[:m.start()] + line + s[m.end():]
    else:
        s = s.rstrip("\n") + "\n" + (("### %s\n" % note) if note else "") + line + "\n"
    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      RM2100.config: %s" % line)

# ---------------------------------------------------------------- 21. Shadowsocks не входит в образ (возврат: CONFIG_FIRMWARE_INCLUDE_SHADOWSOCKS=y)
# Код, страница и пункт меню остаются в дереве; флаг n убирает пакеты (xray и trojan собираются только вместе с ним) и пункт меню.
set_cfg("FIRMWARE_INCLUDE_SHADOWSOCKS", "n", "Shadowsocks: n = не входит в образ (xray и trojan собираются только при y)")

# ---------------------------------------------------------------- 22. Русский язык в интерфейсе (RU.dict уже есть в дереве); китайский убран
set_cfg("FIRMWARE_INCLUDE_LANG_RU", "y")
set_cfg("FIRMWARE_INCLUDE_LANG_CN", "n")

# ---------------------------------------------------------------- 23. OpenVPN в образе: флаг, страницы VPN Server/Client и пункты меню
set_cfg("FIRMWARE_INCLUDE_OPENVPN", "y")

def openvpn_pages():
    # 23a. www/Makefile: vpnsrv.asp и vpncli.asp не удалять при OpenVPN
    rel = "trunk/user/www/Makefile"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel)
    else:
        raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
        if "CONFIG_FIRMWARE_INCLUDE_OPENVPN" in s and "ng-port: openvpn pages" in s: print("уже есть     www/Makefile: страницы VPN для OpenVPN")
        else:
            a1 = "ifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_SERVER) $(CONFIG_FIRMWARE_INCLUDE_AMNEZIAWG)))\n\trm -f $(INSTALLDIR)/www/vpnsrv.asp"
            a2 = "ifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT) $(CONFIG_FIRMWARE_INCLUDE_AMNEZIAWG)))\n\trm -f $(INSTALLDIR)/www/vpncli.asp"
            o1 = "# ng-port: openvpn pages\nifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_SERVER) $(CONFIG_FIRMWARE_INCLUDE_AMNEZIAWG) $(CONFIG_FIRMWARE_INCLUDE_OPENVPN)))\n\trm -f $(INSTALLDIR)/www/vpnsrv.asp"
            o2 = "ifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT) $(CONFIG_FIRMWARE_INCLUDE_AMNEZIAWG) $(CONFIG_FIRMWARE_INCLUDE_OPENVPN)))\n\trm -f $(INSTALLDIR)/www/vpncli.asp"
            if a1 in s and a2 in s:
                s = s.replace("# ng-port: vpn pages\n" + a1, o1, 1) if ("# ng-port: vpn pages\n" + a1) in s else s.replace(a1, o1, 1)
                s = s.replace(a2, o2, 1); wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      www/Makefile: vpnsrv.asp и vpncli.asp остаются при OpenVPN")
            else:
                # правило 10 не применялось (нет AmneziaWG-блоков) — меняем исходные условия SoftEther
                b1 = "ifneq ($(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_SERVER),y)\n\trm -f $(INSTALLDIR)/www/vpnsrv.asp\nendif\n"
                b2 = "ifneq ($(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT),y)\n\trm -f $(INSTALLDIR)/www/vpn_clients.asp\n\trm -f $(INSTALLDIR)/www/vpncli.asp\nendif\n"
                if b1 in s and b2 in s:
                    s = s.replace(b1, "# ng-port: openvpn pages\nifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_SERVER) $(CONFIG_FIRMWARE_INCLUDE_OPENVPN)))\n\trm -f $(INSTALLDIR)/www/vpnsrv.asp\nendif\n", 1)
                    s = s.replace(b2, "ifneq ($(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT),y)\n\trm -f $(INSTALLDIR)/www/vpn_clients.asp\nendif\nifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_SOFTETHERVPN_CLIENT) $(CONFIG_FIRMWARE_INCLUDE_OPENVPN)))\n\trm -f $(INSTALLDIR)/www/vpncli.asp\nendif\n", 1)
                    wr(p, s.replace("\n", "\r\n") if crlf else s); print("сделано      www/Makefile: vpnsrv.asp и vpncli.asp остаются при OpenVPN")
                else: print("НЕ НАЙДЕНО   www/Makefile: блоки удаления vpnsrv.asp/vpncli.asp")
    # 23b. web_ex.c: found_app_vpnsvr / found_app_vpncli также при APP_OPENVPN
    rel = "trunk/user/httpd/web_ex.c"; p = os.path.join(REPO, rel)
    if not os.path.exists(p): print("НЕТ ФАЙЛА    %s" % rel); return
    s = rd(p)
    pat = re.compile(r"#if (defined ?\([A-Z_0-9]+\)(?: \|\| defined ?\([A-Z_0-9]+\))*)(\r?\n\s*int found_app_vpn(?:svr|cli) = 1;)")
    def sub(m):
        if "APP_OPENVPN" in m.group(1): return m.group(0)
        return "#if %s || defined (APP_OPENVPN)%s" % (m.group(1), m.group(2))
    new, n = pat.subn(sub, s)
    if new != s: wr(p, new); print("сделано      web_ex.c: пункты меню VPN Server/Client для OpenVPN")
    elif n: print("уже есть     web_ex.c: меню VPN для OpenVPN")
    else: print("НЕ НАЙДЕНО   web_ex.c: блоки found_app_vpnsvr/found_app_vpncli")
openvpn_pages()

# ---------------------------------------------------------------- 24. DNSCrypt, DoT (stubby), DoH в образе
# Пакеты, rc/httpd-код, страницы и словари переносит port-dns-services.py; здесь только флаги профиля.
set_cfg("FIRMWARE_INCLUDE_DNSCRYPT", "y", "DNSCrypt proxy ~0.5MB")
set_cfg("FIRMWARE_INCLUDE_STUBBY", "y", "Stubby DNS-over-TLS (DoT) ~0.4MB")
set_cfg("FIRMWARE_INCLUDE_DOH", "y", "doh_proxy DNS-over-HTTPS (DoH) ~0.5MB")

# ---------------------------------------------------------------- 33. Программа openssl в образе RM2100 выключена
# Проверено: wget из busybox 1.24 по https через openssl s_client не скачивает файл (rc=0, файл не создаётся), поэтому IPSet
# качает через curl (он в образе), а openssl только увеличивал бы образ (+~0.4MB). Если правило 33 уже ставило y, возвращаем n.
# Включить позже (вместе с обновлением OpenSSL): CONFIG_FIRMWARE_INCLUDE_OPENSSL_EXE=y в trunk/configs/templates/RM2100.config.
set_cfg("FIRMWARE_INCLUDE_OPENSSL_EXE", "n")
