#!/usr/bin/env python3
"""
Перенос сервиса IPSet из padavan-ng в padavan-4.4.

Что делает (каждая правка идемпотентна, повторный запуск ничего не меняет):
  * -DSUPPORT_IPSET рядом с -DUSE_IPSET (cflags.mk) — включает вкладку «IPSet», раздел в dnsmasq и бэкенд;
  * ipset.sh (загрузка списков, менеджер) + файлы по умолчанию (ipset.json, ipset_post_script.sh, dnsmasq.ipset),
    установка в /usr/bin и /usr/share/ipset, создание /etc/storage/ipset и dnsmasq/dnsmasq.ipset (mtd_storage.sh);
  * rc: start/stop/restart_ipset, обработчики уведомлений restart_ipset / flush_ipset_dhcpd, таймер в watchdog
    (период ipset_period часов), подключение conf-file=dnsmasq.ipset и создание наборов в dnsmasq;
  * httpd: чтение/запись файлов ipsetes.*, dnsmasq.ipset, переменные ipset_enable / ipset_period,
    get_ipset_list_hook (список наборов для страниц Zapret/Proxy/VPN-клиент);
    в 4.4 все 64 бита событий EVM_* заняты, поэтому перезапуск и сброс наборов запускаются без новых битов;
  * страница «Дополнительные настройки DHCP»: редактор dnsmasq.ipset; словари; удаление страницы IPSet при IPSET=n.

Регулярные выражения dnsmasq (ipset=/:.*youtube.*:/...) работают только в dnsmasq 2.93 с патчами regex из ng
(их ставит port-dnsmasq.py, флаг CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX=y). В образ попадает исходный dnsmasq.ipset
из ng, а без этого флага — вариант user/ipset/dnsmasq.ipset.noregex (regex заменены обычными доменами).

  python3 port-ipset.py <путь_к_padavan-ng> <путь_к_padavan-4.4>
"""
import os, re, shutil, sys

if len(sys.argv) < 3: print(__doc__); sys.exit(1)
NG, N44 = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
for d in (NG, N44):
    if not os.path.isdir(os.path.join(d, "trunk")): print("ОШИБКА: нет %s/trunk" % d); sys.exit(1)

U = "trunk/user"
W = U + "/www/n56u_ribbon_fixed"
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

def ins(rel, name, anchor, text, marker, where="after", occ=0, root=None, quiet=False):
    """Вставка text до/после совпадения anchor (регулярка, MULTILINE). Идемпотентно по marker."""
    root = root or N44
    s, crlf = load(root, rel)
    if s is None: step("НЕТ ФАЙЛА", "%s (%s)" % (name, rel)); return False
    if text is None: step("НЕТ В NG", name); return False
    if marker in s: step("уже есть", name); return True
    ms = list(re.finditer(anchor, s, re.M))
    if len(ms) <= occ:
        if not quiet: step("НЕ НАЙДЕНО", "%s: якорь %r (%s)" % (name, anchor[:70], rel))
        return False
    m = ms[occ]; pos = m.end() if where == "after" else m.start()
    save(root, rel, s[:pos] + text + s[pos:], crlf); step("сделано", name); return True

def sub(rel, name, old, new, marker):
    """Точная замена одного вхождения old на new. Идемпотентно по marker."""
    s, crlf = load(N44, rel)
    if s is None: step("НЕТ ФАЙЛА", "%s (%s)" % (name, rel)); return False
    if marker in s: step("уже есть", name); return True
    if s.count(old) < 1: step("НЕ НАЙДЕНО", "%s: фрагмент (%s)" % (name, rel)); return False
    save(N44, rel, s.replace(old, new, 1), crlf); step("сделано", name); return True

# ================================================================ 1. флаг сборки
ins(U + "/shared/cflags.mk", "cflags.mk: -DSUPPORT_IPSET", r"^CFLAGS \+= -DUSE_IPSET\n", "CFLAGS += -DSUPPORT_IPSET\n", "-DSUPPORT_IPSET")

# ================================================================ 2. уведомления rc
ins(U + "/shared/notify_rc.h", "notify_rc.h: RCN_RESTART_IPSET / RCN_FLUSH_IPSET_DHCPD",
    r'^#define RCN_RESTART_DHCPD[^\n]*\n',
    '#define RCN_FLUSH_IPSET_DHCPD\t\t"flush_ipset_dhcpd"\n#define RCN_RESTART_IPSET\t\t"restart_ipset"\n', "RCN_RESTART_IPSET")

# ================================================================ 3. пакет ipset: ipset.sh и файлы по умолчанию
IP = U + "/ipset"
src_sh = os.path.join(NG, IP, "ipset.sh")
dst_sh = os.path.join(N44, IP, "ipset.sh")
if os.path.exists(dst_sh): step("уже есть", "ipset/ipset.sh")
elif os.path.exists(src_sh):
    shutil.copyfile(src_sh, dst_sh); os.chmod(dst_sh, 0o755); step("сделано", "скопирован ipset/ipset.sh")
else: step("НЕТ В NG", "ipset/ipset.sh")

CFG = os.path.join(N44, IP, "config")
NGS = os.path.join(NG, U, "scripts/storage")
def put(name, text, mode=0o644):
    p = os.path.join(CFG, name)
    if os.path.exists(p): step("уже есть", "ipset/config/" + name); return
    if text is None: step("НЕТ В NG", "ipset/config/" + name); return
    os.makedirs(CFG, exist_ok=True); wr(p, text); os.chmod(p, mode); step("сделано", "ipset/config/" + name)
def ngtxt(rel):
    p = os.path.join(NGS, rel)
    return rd(p) if os.path.exists(p) else None


# busybox 1.24 в 4.4: wget по https вызывает внешний openssl s_client и не работает (rc=0, файл не создаётся, даже при наличии openssl), а curl в образе есть.
# ipset.sh и ipset_post_script.sh берут curl, если он установлен, иначе остаётся wget.
def fix_cmdv(path, name):
    # busybox 1.24 на роутере: `command -v curl` в скрипте возвращает ошибку (curl при этом есть), поэтому проверяем файл
    if not os.path.exists(path): return
    raw = rd(path)
    if "command -v curl >/dev/null 2>&1" not in raw: return
    wr(path, raw.replace("command -v curl >/dev/null 2>&1", "[ -x /usr/bin/curl ]")); step("сделано", name + ": проверка curl через [ -x ]")

def patch_text(path, name, old, new, mark):
    if not os.path.exists(path): step("НЕТ ФАЙЛА", name); return
    raw = rd(path); txt = raw.replace("\r\n", "\n")
    if mark in txt: step("уже есть", name); return
    if old not in txt: step("НЕ НАЙДЕНО", name + ": фрагмент wget"); return
    wr(path, txt.replace(old, new, 1)); step("сделано", name)

put("ipset.json", ngtxt("ipset/ipset.json"))
put("ipset_post_script.sh", ngtxt("ipset/ipset_post_script.sh"), 0o755)

patch_text(dst_sh, "ipset.sh: curl вместо wget для https",
    '        out=$(wget -T5 --no-check-certificate "$1" -O "$2" 2>&1)\n',
    '        # ng-port: curl (wget в busybox 1.24 не умеет https без openssl)\n'
    '        if [ -x /usr/bin/curl ]; then\n'
    '            out=$(curl -sSLkf --connect-timeout 10 -m 120 "$1" -o "$2" 2>&1)\n'
    '        else\n'
    '            out=$(wget -T5 --no-check-certificate "$1" -O "$2" 2>&1)\n'
    '        fi\n', "ng-port: curl")
patch_text(dst_sh, "ipset.sh: curl, сообщения об ошибках",
    '            *"bad address"*|*"404 Not Found"*|*"403 Forbidden"*)\n',
    '            *"bad address"*|*"404 Not Found"*|*"403 Forbidden"*|*"Could not resolve host"*|*"error: 404"*|*"error: 403"*)\n',
    "Could not resolve host")
patch_text(dst_sh, "ipset.sh: сброс кэша через /proc (busybox sysctl не знает vm.drop_caches)",
    '    sync && sysctl -q vm.drop_caches=3\n',
    '    sync && echo 3 > /proc/sys/vm/drop_caches # ng-port: busybox 1.24 sysctl: unknown key vm.drop_caches\n',
    "/proc/sys/vm/drop_caches")
patch_text(os.path.join(CFG, "ipset_post_script.sh"), "ipset_post_script.sh: curl вместо wget для https",
    '    wget -T10 --no-check-certificate "$1" -O "$2" && return 0 || sleep $r\n',
    '    if [ -x /usr/bin/curl ]; then # ng-port: curl\n'
    '      curl -sSLkf --connect-timeout 10 -m 300 "$1" -o "$2" && return 0 || sleep $r\n'
    '    else\n'
    '      wget -T10 --no-check-certificate "$1" -O "$2" && return 0 || sleep $r\n'
    '    fi\n', "ng-port: curl")

# dnsmasq 2.90 без regex: записи вида :.*слово.*: заменяем обычными доменами (поддомены dnsmasq учитывает сам)
RX = {"youtube": "youtube.com youtube-nocookie.com", "discord": "discord.com discord.gg discordapp.com discordapp.net discord.media",
      "tiktok": "tiktok.com tiktokv.com tiktokcdn.com", "spotify": "spotify.com", "whatsapp": "whatsapp.com whatsapp.net",
      "twitter": "twitter.com", "telegram": "telegram.org telegram.me", "githubusercontent": "githubusercontent.com",
      "linkedin": "linkedin.com"}
def de_regex(txt):
    out = ["### Адаптация ng-port: вариант для dnsmasq без regex (CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX=n), записи :.*слово.*: заменены доменами."]
    for line in txt.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^(\s*ipset=/)(.*)(/[^/]+)\s*$", line)
        if not m or ":" not in m.group(2): out.append(line); continue
        toks = []
        for t in m.group(2).split("/"):
            if t.startswith(":") and t.endswith(":") and len(t) > 2:
                w = re.sub(r"[^A-Za-z0-9]", "", t)
                toks += RX.get(w, "").split()
            elif t: toks.append(t)
        seen = []; [seen.append(t) for t in toks if t not in seen]
        if seen: out.append(m.group(1) + "/".join(seen) + m.group(3))
        else: out.append("# (удалено, требовался regex) " + line.strip())
    return "\n".join(out)
t = ngtxt("dnsmasq/dnsmasq.ipset")
p_cfg = os.path.join(CFG, "dnsmasq.ipset")
if t is not None and os.path.exists(p_cfg) and rd(p_cfg).startswith("### Адаптация ng-port"):
    wr(p_cfg, t); step("сделано", "ipset/config/dnsmasq.ipset: возвращён оригинал ng (regex)")
else:
    put("dnsmasq.ipset", t)
p_nr = os.path.join(N44, IP, "dnsmasq.ipset.noregex")
if os.path.exists(p_nr): step("уже есть", "ipset/dnsmasq.ipset.noregex")
elif t is None: step("НЕТ В NG", "ipset/dnsmasq.ipset.noregex")
else: wr(p_nr, de_regex(t)); os.chmod(p_nr, 0o644); step("сделано", "ipset/dnsmasq.ipset.noregex (без regex)")

ins(IP + "/Makefile", "ipset/Makefile: установка ipset.sh и файлов по умолчанию",
    r"^\t\$\(ROMFSINST\) \$\(THISDIR\)/\$\(SRC_NAME\)/src/ipset /sbin/ipset\n",
    "\t$(ROMFSINST) -p +x /usr/bin/ipset.sh\n\t$(ROMFSINST) -d config /usr/share/ipset\n", "/usr/bin/ipset.sh")
ins(IP + "/Makefile", "ipset/Makefile: dnsmasq.ipset без regex, если regex в dnsmasq выключен",
    r"^\t\$\(ROMFSINST\) -d config /usr/share/ipset\n",
    "ifneq ($(CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX),y)\n\t$(ROMFSINST) dnsmasq.ipset.noregex /usr/share/ipset/dnsmasq.ipset\nendif\n", "dnsmasq.ipset.noregex")

# файлы в /etc/storage (создаются при первом запуске, если их ещё нет)
ins(U + "/scripts/mtd_storage.sh", "mtd_storage.sh: создание /etc/storage/ipset и dnsmasq.ipset", r"^\t# create zapret files\n",
    '''\t# create ipset files (ng-port: ipset)
\tif [ -d "/usr/share/ipset" ]; then
\t\t[ -d "$dir_storage/ipset" ] || mkdir -p -m 755 "$dir_storage/ipset"
\t\t[ -d "$dir_dnsmasq" ] || mkdir -p -m 755 "$dir_dnsmasq"
\t\tfor i in ipset.json ipset_post_script.sh ; do
\t\t\t[ -f "$dir_storage/ipset/$i" ] || cp -f "/usr/share/ipset/$i" "$dir_storage/ipset/$i"
\t\tdone
\t\tchmod 644 "$dir_storage/ipset/ipset.json" 2>/dev/null
\t\tchmod 755 "$dir_storage/ipset/ipset_post_script.sh" 2>/dev/null
\t\t[ -f "$dir_dnsmasq/dnsmasq.ipset" ] || cp -f "/usr/share/ipset/dnsmasq.ipset" "$dir_dnsmasq/dnsmasq.ipset"
\t\tchmod 644 "$dir_dnsmasq/dnsmasq.ipset" 2>/dev/null
\tfi
''', "ng-port: ipset", where="before")

# ================================================================ 4. rc
RC = U + "/rc/rc.c"
ins(RC, "rc.c: обработчик уведомления restart_ipset", r"^\t\t\trestart_zapret\(\);\n\t\t\}\n#endif\n",
    '#if defined (SUPPORT_IPSET)\n\t\telse if (strcmp(entry->d_name, RCN_RESTART_IPSET) == 0)\n\t\t{\n\t\t\trestart_ipset();\n\t\t}\n#endif\n',
    "RCN_RESTART_IPSET) == 0")
ins(RC, "rc.c: обработчик flush_ipset_dhcpd (сброс наборов dnsmasq)",
    r"^\t\telse if \(strcmp\(entry->d_name, RCN_RESTART_DHCPD\) == 0\)\n\t\t\{\n\t\t\tif \(get_ap_mode\(\)\)\n\t\t\t\tupdate_hosts_ap\(\);\n\t\t\trestart_dhcpd\(\);\n\t\t\}\n",
    '''#if defined (SUPPORT_IPSET)
\t\telse if (strcmp(entry->d_name, RCN_FLUSH_IPSET_DHCPD) == 0)
\t\t{
\t\t\tdoSystem("sed -n 's#^[[:space:]]*ipset=/.*/##p' /etc/storage/dnsmasq/dnsmasq.ipset"
\t\t\t\t "| tr ',' '\\\\n' | sort -u"
\t\t\t\t "| xargs -r -I '{}' ipset -q flush '{}'");
\t\t}
#endif
''', "RCN_FLUSH_IPSET_DHCPD) == 0")
ins(RC, "rc.c: команда restart_ipset (кнопка на странице)", r"^\t\trestart_zapret\(\);\n\t\}\n#endif\n",
    '#if defined(SUPPORT_IPSET)\n\telse if (!strcmp(base, RCN_RESTART_IPSET)) {\n\t\tnotify_rc(RCN_RESTART_IPSET);\n\t}\n#endif\n',
    "!strcmp(base, RCN_RESTART_IPSET)")

# Кнопка «Обновить» на вкладке IPSet выполняет команду restart_ipset через SystemCmd, поэтому нужна ссылка /sbin/restart_ipset -> rc
# (как restart_zapret). Без неё в консоли «restart_ipset: not found» и ничего не происходит.
ins(U + "/rc/Makefile", "rc/Makefile: ссылка /sbin/restart_ipset",
    r"^\tcd \$\(INSTALLDIR\)/sbin && ln -sf rc restart_zapret\n",
    "\tcd $(INSTALLDIR)/sbin && ln -sf rc restart_ipset\n", "ln -sf rc restart_ipset")

SV = U + "/rc/services.c"
ins(SV, "services.c: start/stop/restart_ipset", r"^void reload_zapret\(void\)\{\n[^\n]*\n[^\n]*\n\}\n#endif\n",
    '''
#if defined (SUPPORT_IPSET)
int is_ipset_run(void){
\tif (pids("ipset"))
\t\treturn 1;
\treturn 0;
}

void stop_ipset(void){
\teval("/usr/bin/ipset.sh", "stop");
}

void start_ipset(void){
\tif (!get_ap_mode() && nvram_get_int("ipset_enable") == 1)
\t\tsystem("/usr/bin/ipset.sh start &");
}

void restart_ipset(void){
\tstop_ipset();
\tstart_ipset();
}
#endif
''', "void restart_ipset(void)")
ins(SV, "services.c: stop_ipset() в stop_services", r"^\tstop_zapret\(\);\n#endif\n",
    '#if defined (SUPPORT_IPSET)\n\tstop_ipset();\n#endif\n', "#if defined (SUPPORT_IPSET)\n\tstop_ipset();\n#endif")

ins(U + "/rc/rc.h", "rc.h: объявления ipset", r"^void reload_zapret\(void\);\n#endif\n",
    '#if defined (SUPPORT_IPSET)\nint is_ipset_run(void);\nvoid stop_ipset(void);\nvoid start_ipset(void);\nvoid restart_ipset(void);\n#endif\n',
    "void restart_ipset(void)")

WD = U + "/rc/watchdog.c"
ins(WD, "watchdog.c: ipset_timer", r"^static int ntpc_timer = -1;\n",
    '#if defined (SUPPORT_IPSET)\nstatic int ipset_timer = -1;\n#endif\n', "static int ipset_timer")
ins(WD, "watchdog.c: ipset_handler", r"^static void\ninet_handler\(int is_ap_mode\)\n",
    '''#if defined (SUPPORT_IPSET)
static void
ipset_handler(void)
{
\tint ipset_period = nvram_get_int("ipset_period");

\tif (ipset_period < 1)
\t\treturn;

\tif (ipset_period > 336)
\t\tipset_period = 336; // max two weeks

\tipset_period = ipset_period * 360;

\t// update ipset every period time
\tipset_timer = (ipset_timer + 1) % ipset_period;
\tif (ipset_timer == 0) {
\t\tnotify_rc(RCN_RESTART_IPSET);
\t}
}
#endif

''', "ipset_handler(void)", where="before")
ins(WD, "watchdog.c: вызов ipset_handler()", r"^\t\t\tntpc_handler\(\);\n(?=#if defined \(APP_AMNEZIAWG\))",
    '#if defined (SUPPORT_IPSET)\n\t\t\tipset_handler();\n#endif\n', "\t\t\tipset_handler();")

ins(U + "/rc/services_ex.c", "services_ex.c: conf-file=dnsmasq.ipset и наборы dnsmasq", r'^\tfprintf\(fp, "conf-file=%s/dnsmasq\.conf\\n", storage_dir\);\n',
    '''#if defined (SUPPORT_IPSET)
\t{
\t\tchar ipset_conf[64];
\t\tsnprintf(ipset_conf, sizeof(ipset_conf), "%s/dnsmasq.ipset", storage_dir);
\t\tif (access(ipset_conf, F_OK) == 0) {
\t\t\tfprintf(fp, "conf-file=%s\\n", ipset_conf);

\t\t\t// create dnsmasq ipsets, timeout 6h
\t\t\tdoSystem("sed -n 's#^[[:space:]]*ipset=/.*/##p' %s/dnsmasq.ipset"
\t\t\t\t "| tr ',' '\\\\n' | sort -u"
\t\t\t\t "| xargs -r -I '{}' ipset -q create '{}' nethash timeout 21600",
\t\t\t\t storage_dir);
\t\t}
\t}
#endif
''', "dnsmasq.ipset")

# ================================================================ 5. httpd
ins(U + "/httpd/httpd.h", "httpd.h: STORAGE_IPSET_DIR", r'^#define STORAGE_ZAPRET_DIR[^\n]*\n',
    '#define STORAGE_IPSET_DIR\t"/etc/storage/ipset"\n', "STORAGE_IPSET_DIR")

WE = U + "/httpd/web_ex.c"
ins(WE, "web_ex.c: чтение файлов ipsetes.*", r'^\telse if \(strncmp\(file, "zapretc\.", 8\)==0\)\n\t\tsnprintf\([^\n]*\n',
    '\telse if (strncmp(file, "ipsetes.", 8)==0)\n\t\tsnprintf(filename, sizeof(filename), "%s/%s", STORAGE_IPSET_DIR, file+8);\n', '"ipsetes.", 8)==0')

# флаги уведомлений без новых битов EVM_* (все 64 бита заняты)
ins(WE, "web_ex.c: флаги ipset_notify", r"^static u64 restart_needed_bits = 0;\n",
    '/* ng-port: перезапуск/сброс IPSet без новых битов EVM_* (все 64 заняты) */\n#define IPSET_NOTIFY_RESTART\t1\n#define IPSET_NOTIFY_FLUSH\t2\nstatic int ipset_notify = 0;\n',
    "ipset_notify = 0;")

sub(WE, "web_ex.c: запись dnsmasq.ipset → сброс наборов",
    '\t\t\t\tif (write_textarea_to_file(value, STORAGE_DNSMASQ_DIR, file_name))\n\t\t\t\t\trestart_needed_bits |= event_mask;\n',
    '\t\t\t\tif (write_textarea_to_file(value, STORAGE_DNSMASQ_DIR, file_name)) {\n\t\t\t\t\trestart_needed_bits |= event_mask;\n'
    '#if defined(SUPPORT_IPSET)\n\t\t\t\t\tif (!strcmp(file_name, "dnsmasq.ipset"))\n\t\t\t\t\t\tipset_notify |= IPSET_NOTIFY_FLUSH;\n#endif\n\t\t\t\t}\n',
    "ipset_notify |= IPSET_NOTIFY_FLUSH;")

ins(WE, "web_ex.c: запись файлов ipsetes.*", r'^#if defined\(APP_OPENVPN\)\n\t\t\telse if \(!strncmp\(v->name, "ovpnsvr\.", 8\)\) \{',
    '''#if defined(SUPPORT_IPSET)
\t\t\telse if (!strncmp(v->name, "ipsetes.", 8)) {
\t\t\t\tif (write_textarea_to_file(value, STORAGE_IPSET_DIR, file_name)) {
\t\t\t\t\tipset_notify |= IPSET_NOTIFY_RESTART;
\t\t\t\t\tdoSystem("/sbin/mtd_storage.sh save");
\t\t\t\t}
\t\t\t}
#endif
''', '!strncmp(v->name, "ipsetes.", 8)', where="before")

ins(WE, "web_ex.c: ipset_enable → перезапуск", r"^\t\tnvram_set\(v->name, value\);\n\t\tnvram_modified = 1;\n",
    '#if defined(SUPPORT_IPSET)\n\t\tif (!strcmp(v->name, "ipset_enable"))\n\t\t\tipset_notify |= IPSET_NOTIFY_RESTART;\n#endif\n',
    '!strcmp(v->name, "ipset_enable")')

sub(WE, "web_ex.c: validate_asp_apply учитывает ipset_notify",
    "\treturn (nvram_modified || restart_needed_bits) ? 1 : 0;\n", "\treturn (nvram_modified || restart_needed_bits || ipset_notify) ? 1 : 0;\n", "restart_needed_bits || ipset_notify")

sub(WE, "web_ex.c: сброс ipset_notify при начале применения",
    "\trestart_needed_bits = 0;\n\n\t// assign control variables\n", "\trestart_needed_bits = 0;\n\tipset_notify = 0;\n\n\t// assign control variables\n", "\tipset_notify = 0;\n\n\t// assign")

# время ожидания на странице, если изменились только настройки IPSet
sub(WE, "web_ex.c: время ожидания для IPSet",
    '\t\twebsWrite(wp, "<script>restart_needed_time(%u);</script>\\n", restart_total_time);\n\t}\n\n\treturn 0;\n',
    '\t\twebsWrite(wp, "<script>restart_needed_time(%u);</script>\\n", restart_total_time);\n\t}\n'
    '\telse if (ipset_notify != 0 && (!strcmp(action_mode, " Apply ") || !strcmp(action_mode, " Restart "))) {\n'
    '\t\twebsWrite(wp, "<script>restart_needed_time(%d);</script>\\n", 1);\n\t}\n\n\treturn 0;\n',
    "ipset_notify != 0 &&")

sub(WE, "web_ex.c: ej_notify_services — перезапуск IPSet",
    "\tif (!restart_needed_bits)\n\t\treturn 0;\n\n\tif ((restart_needed_bits & EVM_RESTART_REBOOT) != 0) {",
    "\tif (!restart_needed_bits && !ipset_notify)\n\t\treturn 0;\n\n\tif ((restart_needed_bits & EVM_RESTART_REBOOT) != 0) {",
    "!restart_needed_bits && !ipset_notify")
sub(WE, "web_ex.c: ej_notify_services — отправка уведомлений IPSet",
    '\tdbG("debug restart_needed_bits before: 0x%llx\\n", restart_needed_bits);\n',
    '\tdbG("debug restart_needed_bits before: 0x%llx\\n", restart_needed_bits);\n\n'
    '#if defined(SUPPORT_IPSET)\n\tif (ipset_notify & IPSET_NOTIFY_FLUSH)\n\t\tnotify_rc(RCN_FLUSH_IPSET_DHCPD);\n#endif\n',
    "notify_rc(RCN_FLUSH_IPSET_DHCPD)")
sub(WE, "web_ex.c: ej_notify_services — restart_ipset",
    '\tdbG("debug restart_needed_bits after: 0x%llx\\n", restart_needed_bits);\n\n\trestart_needed_bits = 0;\n',
    '\tdbG("debug restart_needed_bits after: 0x%llx\\n", restart_needed_bits);\n\n'
    '#if defined(SUPPORT_IPSET)\n\tif (ipset_notify & IPSET_NOTIFY_RESTART)\n\t\tnotify_rc(RCN_RESTART_IPSET);\n#endif\n'
    '\tipset_notify = 0;\n\trestart_needed_bits = 0;\n',
    "notify_rc(RCN_RESTART_IPSET)")

HOOK = '''static int
get_ipset_list_hook(int eid, webs_t wp, int argc, char **argv)
{
#if defined(SUPPORT_IPSET)
\tFILE *fp;
\tconst char *cmd = "ipset -q -t list | grep -E '^(Name|Number of entries):'";
\tchar line[256] = {0};
\tchar name[128] = {0};
\tchar entries[32] = {0};
\tint first = 1;
\tint waiting_for_entries = 0;

\tfp = popen(cmd, "r");
\tif (fp == NULL) {
\t\treturn 1;
\t}

\twhile (fgets(line, sizeof(line), fp)) {
\t\tline[strcspn(line, "\\r\\n")] = 0;

\t\tif (strncmp(line, "Name: ", 6) == 0) {
\t\t\tsscanf(line + 6, " %127s", name);
\t\t\twaiting_for_entries = 1;
\t\t}
\t\telse if (strncmp(line, "Number of entries: ", 19) == 0 && waiting_for_entries) {
\t\t\tsscanf(line + 19, " %31s", entries);
\t\t\tif (!first) {
\t\t\t\twebsWrite(wp, ",");
\t\t\t}
\t\t\twebsWrite(wp, "{\\"name\\": \\"%s\\", \\"entries\\": \\"%s\\"}", name, entries);
\t\t\tfirst = 0;
\t\t\twaiting_for_entries = 0;
\t\t}
\t}

\tpclose(fp);
#endif
\treturn 0;
}

'''
ins(WE, "web_ex.c: get_ipset_list_hook", r"^static int\nej_firmware_caps_hook\(", HOOK, "get_ipset_list_hook(int eid", where="before")
ins(WE, "web_ex.c: get_ipset_list_hook в таблице", r'^\t\{ "firmware_caps_hook", ej_firmware_caps_hook\},\n',
    '\t{ "get_ipset_list_hook", get_ipset_list_hook},\n', '{ "get_ipset_list_hook"')

# variables.c: в LANHostConfig (страницы шлют sid_list=LANHostConfig;General;Storage;)
VR = U + "/httpd/variables.c"
def vars_table(txt, name):
    m = re.search(r"struct variable %s\[\] = \{\n" % name, txt)
    if not m: return None
    e = txt.find("{0,0,0,0}", m.end())
    return (m.end(), e) if e > 0 else None
s, crlf = load(N44, VR)
if s is None: step("НЕТ ФАЙЛА", VR)
else:
    lan = vars_table(s, "variables_LANHostConfig")
    if not lan: step("НЕ НАЙДЕНО", "variables.c: таблица LANHostConfig")
    else:
        changed = False
        seg = s[lan[0]:lan[1]]
        if '{"ipset_enable"' in seg: step("уже есть", "variables.c: ipset_enable/ipset_period/ipsetes.* (LANHostConfig)")
        else:
            m = re.search(r'^\t\t\t\{"sshd_enable", "", NULL, [^\n]*\n(?:\t\t\t\{"sshd_enable_gp"[^\n]*\n)?', seg, re.M)
            if not m: step("НЕ НАЙДЕНО", "variables.c: якорь sshd_enable в LANHostConfig")
            else:
                blk = ('#if defined(SUPPORT_IPSET)\n\t\t\t{"ipset_enable", "", NULL, FALSE},\n\t\t\t{"ipset_period", "", NULL, FALSE},\n'
                       '\t\t\t{"ipsetes.ipset.json", "File", NULL, FALSE},\n\t\t\t{"ipsetes.ipset_post_script.sh", "File", NULL, FALSE},\n#endif\n')
                pos = lan[0] + m.end(); s = s[:pos] + blk + s[pos:]; changed = True; step("сделано", "variables.c: ipset_enable/ipset_period/ipsetes.* (LANHostConfig)")
        lan = vars_table(s, "variables_LANHostConfig"); seg = s[lan[0]:lan[1]]
        if '"dnsmasq.dnsmasq.ipset"' in seg: step("уже есть", "variables.c: dnsmasq.dnsmasq.ipset")
        else:
            m = re.search(r'^\t\t\t\{"dnsmasq\.dnsmasq\.servers", "File", NULL, [^\n]*\n', seg, re.M)
            if not m: step("НЕ НАЙДЕНО", "variables.c: якорь dnsmasq.dnsmasq.servers в LANHostConfig")
            else:
                pos = lan[0] + m.end()
                s = s[:pos] + '#if defined(SUPPORT_IPSET)\n\t\t\t{"dnsmasq.dnsmasq.ipset", "File", NULL, EVM_RESTART_DHCPD},\n#endif\n' + s[pos:]
                changed = True; step("сделано", "variables.c: dnsmasq.dnsmasq.ipset")
        if changed: save(N44, VR, s, crlf)

# ================================================================ 6. значения по умолчанию
ins(U + "/shared/defaults.c", "defaults.c: ipset_enable / ipset_period", r'^\t\{ "vpnc_sfw", "0" \},\n',
    '#if defined(SUPPORT_IPSET)\n\t{ "ipset_enable", "0" },\n\t{ "ipset_period", "24" },\n#endif\n', '{ "ipset_enable"', where="before")

# ================================================================ 7. www
# JS-функции из ng, без которых страницы с выбором наборов (VPN-клиент, Zapret, Proxy) и кнопка «Обновить» IPSet падают:
# declOfNum (склонение «запись/записи/записей», общий скрипт general.js) и sendSystemCmd (state.js, команда через /apply.cgi).
def port_js_func(rel_js, fname, where):
    ngp = os.path.join(NG, rel_js)
    s_ng = rd(ngp).replace("\r\n", "\n") if os.path.exists(ngp) else None
    m = re.search(r"^function %s\(.*?^\}\n" % fname, s_ng or "", re.M | re.S)
    if not m: step("НЕТ В NG", "%s: function %s" % (rel_js, fname)); return
    fn = m.group(0)
    s44, crlf = load(N44, rel_js)
    if s44 is None: step("НЕТ ФАЙЛА", rel_js); return
    if "function %s(" % fname in s44: step("уже есть", "%s: %s()" % (rel_js, fname)); return
    if where == "end":
        new = s44.rstrip("\n") + "\n\n" + fn
    else:
        i = s44.find(where)
        if i < 0: step("НЕ НАЙДЕНО", "%s: якорь для %s" % (rel_js, fname)); return
        new = s44[:i] + fn + "\n" + s44[i:]
    save(N44, rel_js, new, crlf); step("сделано", "%s: %s()" % (rel_js, fname))
port_js_func(W + "/general.js", "declOfNum", "end")
port_js_func(W + "/state.js", "sendSystemCmd", "function get_ap_mode(){")

# (якорь выбираем по последнему из блоков rm -f страниц «Сервисы»)
s, crlf = load(N44, U + "/www/Makefile")
if s is None: step("НЕТ ФАЙЛА", "www/Makefile")
elif "Advanced_Services_IPSet.asp" in s: step("уже есть", "www/Makefile: удалять страницу IPSet, если IPSET не включён")
else:
    pos = None
    for pg in ("DoT", "DoH", "DNSCrypt", "Zapret"):
        m = re.search(r"^\trm -f \$\(INSTALLDIR\)/www/Advanced_Services_%s\.asp\nendif\n" % pg, s, re.M)
        if m: pos = m.end(); break
    if pos is None: step("НЕ НАЙДЕНО", "www/Makefile: якорь rm -f Advanced_Services_*.asp")
    else:
        save(N44, U + "/www/Makefile", s[:pos] + "ifneq ($(CONFIG_FIRMWARE_INCLUDE_IPSET),y)\n\trm -f $(INSTALLDIR)/www/Advanced_Services_IPSet.asp\nendif\n" + s[pos:], crlf)
        step("сделано", "www/Makefile: удалять страницу IPSet, если IPSET не включён")

# список наборов для страниц Zapret / Proxy / VPN-клиент
for pg in ("Advanced_Services_Zapret", "Advanced_Services_Proxy", "vpncli"):
    rel = "%s/%s.asp" % (W, pg)
    s, crlf = load(N44, rel)
    if s is None: step("НЕТ ФАЙЛА", rel); continue
    if "get_ipset_list_hook" in s: step("уже есть", "%s.asp: список наборов IPSet" % pg); continue
    if "let IPSetList = [];" not in s: step("НЕ НАЙДЕНО", "%s.asp: let IPSetList = [];" % pg); continue
    save(N44, rel, s.replace("let IPSetList = [];", "let IPSetList = [<% get_ipset_list_hook(); %>];", 1), crlf)
    step("сделано", "%s.asp: список наборов IPSet" % pg)

# редактор dnsmasq.ipset на странице DHCP
DH = W + "/Advanced_DHCP_Content.asp"
ROW = '''                                                <tr id="row_dipset">
                                                    <td colspan="2">
                                                        <a href="javascript:spoiler_toggle('spoiler_dipset')"><span>
                                                                <#CustomConf#> "dnsmasq.ipset"
                                                            </span></a>
                                                        <div id="spoiler_dipset" style="display:none;">
                                                            <textarea rows="16" wrap="off" spellcheck="false"
                                                                maxlength="32768" class="span12"
                                                                name="dnsmasq.dnsmasq.ipset"
                                                                style="font-family:'Courier New'; font-size:12px;"><% nvram_dump("dnsmasq.dnsmasq.ipset",""); %></textarea>
                                                        </div>
                                                    </td>
                                                </tr>
'''
ins(DH, "Advanced_DHCP_Content.asp: редактор dnsmasq.ipset", r'^[ \t]*<tr id="row_dservers">\n', ROW, 'id="row_dipset"', where="before")
ins(DH, "Advanced_DHCP_Content.asp: видимость row_dipset (initial)", r"^(\s*)showtext\(\$\(\"LANIP\"\), '<% nvram_get_x\(\"\", \"lan_ipaddr\"\); %>'\);\n",
    "\n            showhide_div('row_dipset', found_support_ipset());\n", "showhide_div('row_dipset', found_support_ipset())")
ins(DH, "Advanced_DHCP_Content.asp: row_dipset в режиме AP", r"^[ \t]*showhide_div\('row_dservers', 0\);\n",
    "                showhide_div('row_dipset', 0);\n", "showhide_div('row_dipset', 0)")

# словари: ключи страницы IPSet и редактора
def parse_dict(path):
    d = {}
    if os.path.exists(path):
        for l in rd(path).replace("\r\n", "\n").split("\n"):
            m = re.match(r"^([A-Za-z0-9_]+)=", l)
            if m: d[m.group(1)] = l
    return d
used_keys = set()
for rel in (W + "/Advanced_Services_IPSet.asp", DH):
    s, _ = load(N44, rel)
    if s: used_keys |= set(re.findall(r"<#([A-Za-z0-9_]+)#>", s))
dng, d44 = os.path.join(NG, U, "www/dict"), os.path.join(N44, U, "www/dict")
if os.path.isdir(dng) and os.path.isdir(d44):
    for fn in sorted(os.listdir(d44)):
        ngd = parse_dict(os.path.join(dng, fn))
        if not ngd: continue
        p = os.path.join(d44, fn); raw = rd(p); crlf = "\r\n" in raw; have = parse_dict(p)
        addl = [ngd[k] for k in sorted(used_keys) if k in ngd and k not in have]
        if addl:
            nl = "\r\n" if crlf else "\n"; body = raw if raw.endswith("\n") or not raw else raw + nl
            wr(p, body + nl.join(addl) + nl); step("сделано", "словарь %s: +%d ключей" % (fn, len(addl)))

fix_cmdv(dst_sh, "ipset.sh")
fix_cmdv(os.path.join(CFG, "ipset_post_script.sh"), "ipset_post_script.sh")

print()
bad = [r for r in results if r[0] in ("НЕ НАЙДЕНО", "НЕТ ФАЙЛА", "НЕТ В NG", "ВНИМАНИЕ")]
print("Итого: %d шагов, из них требуют внимания: %d" % (len(results), len(bad)))
for st, nm in bad: print("  %-11s %s" % (st, nm))
