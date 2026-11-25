#!/usr/bin/env python3
"""
Обновление dnsmasq в padavan-4.4 с 2.90 до 2.93 (как в padavan-ng) с поддержкой regex.

Что делает (идемпотентно):
  * заменяет пакет trunk/user/dnsmasq: Makefile, dnsmasq-2.93.tar.xz и патчи из padavan-ng
    (regex для server= и ipset=, firmware-specific, меньше шума в журнале, сборка без DHCPv6),
    плюс 210-max-procs-4.patch (MAX_PROCS=4 для экономии памяти, как патч 200 в 4.4);
  * удаляет старые файлы 2.90: распакованный каталог dnsmasq-2.90, архив и старые патчи;
  * Makefile пакета ищет libpcre через pkg-config в stage/lib/pkgconfig;
  * trunk/libs/Makefile: libpcre собирается, если CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX=y;
  * профили плат: RM2100 — CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX=y, остальные — n.

  python3 port-dnsmasq.py <путь_к_padavan-ng> <путь_к_padavan-4.4> [<путь_к_210-max-procs-4.patch>]

Патч 210 по умолчанию берётся из каталога скрипта. После запуска: пересобрать (make clean в user/dnsmasq не нужен,
каталог dnsmasq-2.93 распаковывается заново).
"""
import os, re, shutil, sys

if len(sys.argv) < 3: print(__doc__); sys.exit(1)
NG, N44 = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
HERE = os.path.dirname(os.path.abspath(__file__))
P210 = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.join(HERE, "210-max-procs-4.patch")
for d in (NG, N44):
    if not os.path.isdir(os.path.join(d, "trunk")): print("ОШИБКА: нет %s/trunk" % d); sys.exit(1)

results = []
def step(status, name): results.append((status, name)); print("%-13s %s" % (status, name))
def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape", newline="") as f: return f.read()
def wr(p, s):
    with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="") as f: f.write(s)

DM = "trunk/user/dnsmasq"
ngd, d44 = os.path.join(NG, DM), os.path.join(N44, DM)
mk44 = os.path.join(d44, "Makefile")

# ================================================================ 1. пакет dnsmasq 2.93
if not os.path.isdir(ngd) or not os.path.exists(os.path.join(ngd, "dnsmasq-2.93.tar.xz")):
    step("НЕТ В NG", "dnsmasq-2.93.tar.xz в padavan-ng")
elif os.path.exists(mk44) and "dnsmasq-2.93" in rd(mk44):
    step("уже есть", "пакет dnsmasq 2.93")
else:
    # старые файлы 2.90 (в форке распакованный каталог лежит в git)
    for name in os.listdir(d44):
        pth = os.path.join(d44, name)
        if re.match(r"dnsmasq-2\.\d+(\.tar\.xz)?$", name):
            shutil.rmtree(pth) if os.path.isdir(pth) else os.remove(pth); step("сделано", "удалено %s/%s" % (DM, name))
    shutil.rmtree(os.path.join(d44, "patches"), ignore_errors=True)
    shutil.copytree(os.path.join(ngd, "patches"), os.path.join(d44, "patches"))
    shutil.copyfile(os.path.join(ngd, "dnsmasq-2.93.tar.xz"), os.path.join(d44, "dnsmasq-2.93.tar.xz"))
    mk = rd(os.path.join(ngd, "Makefile"))
    # libpcre ищется через pkg-config в stage (в 4.4 нет глобального PKG_CONFIG_LIBDIR)
    old = "\t$(MAKE) -j$(HOST_NCPU) -C $(SRC_NAME) COPTS="
    if old not in mk: step("НЕ НАЙДЕНО", "Makefile ng: строка сборки"); mk_ok = False
    else:
        mk = mk.replace(old, "\tPKG_CONFIG_LIBDIR=$(STAGEDIR)/lib/pkgconfig PKG_CONFIG_PATH=$(STAGEDIR)/lib/pkgconfig \\\n\t$(MAKE) -j$(HOST_NCPU) -C $(SRC_NAME) COPTS=", 1)
        wr(mk44, mk); step("сделано", "пакет dnsmasq: Makefile, dnsmasq-2.93.tar.xz, patches (из padavan-ng)")
if os.path.isdir(os.path.join(d44, "patches")):
    dst = os.path.join(d44, "patches", "210-max-procs-4.patch")
    if os.path.exists(dst): step("уже есть", "patches/210-max-procs-4.patch")
    elif not os.path.exists(P210): step("НЕТ ФАЙЛА", "210-max-procs-4.patch (положите рядом со скриптом или передайте третьим аргументом)")
    else: shutil.copyfile(P210, dst); step("сделано", "patches/210-max-procs-4.patch (MAX_PROCS=4)")

# ================================================================ 2. libpcre для regex
lm = os.path.join(N44, "trunk/libs/Makefile")
if not os.path.exists(lm): step("НЕТ ФАЙЛА", "trunk/libs/Makefile")
else:
    raw = rd(lm); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
    if "ENABLE_DNSMASQ_REGEX" in s: step("уже есть", "libs/Makefile: libpcre для dnsmasq regex")
    else:
        m = re.search(r"^LIBS_INCLUDE_LIBSODIUM=n\n", s, re.M)
        if not m: step("НЕ НАЙДЕНО", "libs/Makefile: якорь LIBS_INCLUDE_LIBSODIUM=n")
        else:
            s = s[:m.end()] + "ifeq ($(CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX),y)\nLIBS_INCLUDE_LIBPCRE=y\nendif\n" + s[m.end():]
            wr(lm, s.replace("\n", "\r\n") if crlf else s); step("сделано", "libs/Makefile: libpcre собирается при DNSMASQ_REGEX=y")

# ================================================================ 3. профили плат
td = os.path.join(N44, "trunk/configs/templates")
if not os.path.isdir(td): step("НЕТ ФАЙЛА", "trunk/configs/templates")
else:
    changed = 0
    for fn in sorted(os.listdir(td)):
        if not fn.endswith(".config"): continue
        p = os.path.join(td, fn); raw = rd(p); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n")
        if re.search(r"^[ \t]*#?[ \t]*CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX[= ]", s, re.M): continue
        val = "y" if fn == "RM2100.config" else "n"
        add = "\n### Enable dnsmasq regex feature (needs libpcre). ~0.2MB\nCONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX=%s\n" % val
        m = re.search(r"^[ \t]*#?[ \t]*CONFIG_FIRMWARE_INCLUDE_IPSET=.*\n", s, re.M)
        s = (s[:m.end()] + add + s[m.end():]) if m else (s.rstrip("\n") + "\n" + add)
        wr(p, s.replace("\n", "\r\n") if crlf else s); changed += 1
    step("сделано" if changed else "уже есть", "профили плат: CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX (RM2100=y, остальные n)%s" % (": %d файлов" % changed if changed else ""))

print()
bad = [r for r in results if r[0] in ("НЕ НАЙДЕНО", "НЕТ ФАЙЛА", "НЕТ В NG", "ВНИМАНИЕ")]
print("Итого: %d шагов, из них требуют внимания: %d" % (len(results), len(bad)))
for st, nm in bad: print("  %-11s %s" % (st, nm))
