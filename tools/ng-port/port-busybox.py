#!/usr/bin/env python3
"""
Обновление BusyBox в padavan-4.4 с 1.24.x (2015) до 1.38.0, как в padavan-ng. Идемпотентно.

Что делает:
  * trunk/user/busybox: прежний Makefile переименован в Makefile.1.24 (пакет busybox-1.24.x не трогается),
    новый Makefile выбирает версию по флагу CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y (иначе 1.24.x);
    Makefile.1.38 скачивает busybox-1.38.0.tar.bz2 с busybox.net (проверка SHA-256, в git не кладётся),
    накладывает патчи ng (patches/, 18 штук: dhcp6c, udhcpc, ntpd, syslogd, init и др.) и собирает;
  * trunk/configs/boards/busybox-1.38.config: конфиг ng (прежний busybox.config для 1.24.x не меняется);
  * trunk/configure: при флаге выбирает конфиг 1.38 и кладёт его в user/busybox/busybox.config,
    включает встроенный HTTPS в wget (без openssl s_client), отключает swapon/swapoff там же, где SWAPONOFF;
  * профили плат: у всех плат CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y (n или отсутствие строки возвращает 1.24.x);
    собирался и проверялся только RM2100.

  python3 port-busybox.py <путь_к_padavan-ng> <путь_к_padavan-4.4>

Из конфига ng отсутствуют (по сравнению с 1.24.x профиля): getopts в ash, base64, getopt, groups, hexdump, id, modinfo,
nohup, sha256sum, telnet, unzip; скрипты прошивки (trunk/user) их не вызывают. После смены версии нужна
полная пересборка busybox: make -C trunk/user/busybox clean (или удалить каталог busybox-1.38.0).
"""
import os, re, shutil, sys

if len(sys.argv) < 3: print(__doc__); sys.exit(1)
NG, N44 = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
for d in (NG, N44):
    if not os.path.isdir(os.path.join(d, "trunk")): print("ОШИБКА: нет %s/trunk" % d); sys.exit(1)

BB_NAME = "busybox-1.38.0"
BB_SHA = "34f9ea6ff8636f2c9241153b9114eefa9e65674a45318ae1ef95bb5f31c53bb2"   # sha256 тарболла из репозитория ng

def step(status, name): print("%-13s %s" % (status, name))
def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape", newline="") as f: return f.read()
def wr(p, s):
    with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="") as f: f.write(s)

BB = os.path.join(N44, "trunk/user/busybox")
NGBB = os.path.join(NG, "trunk/user/busybox")
for p in (os.path.join(NGBB, "patches"), os.path.join(N44, "trunk/configs/boards/busybox.config")):
    if not os.path.exists(p): print("ОШИБКА: нет %s" % p); sys.exit(1)

# ================================================================ 1. Makefile.1.24 (прежний) и диспетчер
mk, mk124 = os.path.join(BB, "Makefile"), os.path.join(BB, "Makefile.1.24")
DISPATCH = '''# ng-port: версия BusyBox выбирается флагом профиля CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y (иначе 1.24.x)
ifeq ($(CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138),y)
include Makefile.1.38
else
include Makefile.1.24
endif
'''
if os.path.exists(mk124):
    step("уже есть", "busybox/Makefile.1.24")
elif not os.path.exists(mk) or "busybox-1.24.x" not in rd(mk):
    step("НЕ НАЙДЕНО", "busybox/Makefile с busybox-1.24.x (ожидался прежний пакет)")
else:
    shutil.move(mk, mk124); step("сделано", "busybox/Makefile -> Makefile.1.24")
if os.path.exists(mk) and "include Makefile.1.38" in rd(mk): step("уже есть", "busybox/Makefile (диспетчер версий)")
else: wr(mk, DISPATCH); step("сделано", "busybox/Makefile (диспетчер версий)")

# ================================================================ 2. Makefile.1.38
MK138 = '''# BusyBox 1.38 (https://busybox.net). Перенос из padavan-ng: те же патчи, конфиг приходит от trunk/configure
# (user/busybox/busybox.config), тарболл скачивается при сборке и проверяется по SHA-256.
SRC_NAME = %(name)s
SRC_URL = https://busybox.net/downloads/$(SRC_NAME).tar.bz2
SRC_SHA256 = %(sha)s

CFLAGS += -ffunction-sections -fdata-sections -fvisibility=hidden
LDFLAGS += -Wl,--gc-sections

all: download_test extract_test
	cp -fL busybox.config $(SRC_NAME)/.config
	$(MAKE) -j$(HOST_NCPU) -C $(SRC_NAME)

download_test:
	( if [ ! -f $(SRC_NAME).tar.bz2 ]; then \\
		wget -t5 -T40 -O $(SRC_NAME).tar.bz2 $(SRC_URL) \\
			|| rm -f $(SRC_NAME).tar.bz2; \\
	fi; \\
	if [ -f $(SRC_NAME).tar.bz2 ] && [ "`sha256sum $(SRC_NAME).tar.bz2 | cut -d' ' -f1`" != "$(SRC_SHA256)" ]; then \\
		echo "$(SRC_NAME).tar.bz2: wrong SHA-256, removed"; \\
		rm -f $(SRC_NAME).tar.bz2; \\
	fi; \\
	[ -f $(SRC_NAME).tar.bz2 ] )

extract_test:
	( if [ ! -d $(SRC_NAME) ]; then \\
		tar xjf $(SRC_NAME).tar.bz2 && \\
		cat patches/*.patch | patch -d $(SRC_NAME) -r - -N -p1; \\
	fi )

clean:
	( if [ -d $(SRC_NAME) ]; then $(MAKE) -C $(SRC_NAME) distclean; fi )

romfs:
	$(MAKE) -C $(SRC_NAME) CONFIG_PREFIX=$(ROMFSDIR) install
''' % {"name": BB_NAME, "sha": BB_SHA}
p = os.path.join(BB, "Makefile.1.38")
if os.path.exists(p) and rd(p) == MK138: step("уже есть", "busybox/Makefile.1.38")
else: wr(p, MK138); step("сделано", "busybox/Makefile.1.38")

# ================================================================ 3. патчи ng
src, dst = os.path.join(NGBB, "patches"), os.path.join(BB, "patches")
os.makedirs(dst, exist_ok=True)
changed = 0
for name in sorted(os.listdir(src)):
    if not name.endswith(".patch"): continue
    a, b = os.path.join(src, name), os.path.join(dst, name)
    if os.path.exists(b) and open(a, "rb").read() == open(b, "rb").read(): continue
    shutil.copyfile(a, b); changed += 1
step("сделано" if changed else "уже есть", "busybox/patches (%d файл(ов) обновлено)" % changed if changed else "busybox/patches")

# ================================================================ 4. конфиг 1.38
cfg = os.path.join(N44, "trunk/configs/boards/busybox-1.38.config")
ngcfg = os.path.join(NG, "trunk/configs/boards/busybox.config")
if os.path.exists(cfg) and open(cfg, "rb").read() == open(ngcfg, "rb").read(): step("уже есть", "configs/boards/busybox-1.38.config")
else: shutil.copyfile(ngcfg, cfg); step("сделано", "configs/boards/busybox-1.38.config (из ng)")

# ================================================================ 5. configure
rel = os.path.join(N44, "trunk/configure")
raw = rd(rel); crlf = "\r\n" in raw; s = raw.replace("\r\n", "\n"); orig = s

# 5a. выбор конфига сразу после чтения .config проекта
MARK_A = "ng-port: BusyBox 1.38"
if MARK_A in s: step("уже есть", "configure: выбор конфига BusyBox 1.38")
else:
    anchor = "# load project root config\n. $ROOTDIR/.config\n"
    if anchor not in s: step("НЕ НАЙДЕНО", "configure: якорь '. $ROOTDIR/.config'")
    else:
        s = s.replace(anchor, anchor + '''
# ng-port: BusyBox 1.38 (CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y); по умолчанию 1.24.x
if [ "$CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138" = "y" ] ; then
	busybox_cf="$ROOTDIR/configs/boards/busybox-1.38.config"
	busybox_tf="$ROOTDIR/user/busybox/busybox.config"
fi
''', 1)
        step("сделано", "configure: выбор конфига BusyBox 1.38")

# 5b. встроенный HTTPS в wget вместо openssl s_client (сразу после копирования конфига)
MARK_B = "ng-port: wget HTTPS"
if MARK_B in s: step("уже есть", "configure: встроенный HTTPS в wget")
else:
    anchor = 'cp -fL "$busybox_cf" "$busybox_tf"\n'
    if anchor not in s: step("НЕ НАЙДЕНО", "configure: якорь cp busybox_cf")
    else:
        s = s.replace(anchor, anchor + '''# ng-port: wget HTTPS средствами самого BusyBox 1.38 (без программы openssl)
if [ "$CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138" = "y" ] ; then
	func_enable_busybox_param "CONFIG_FEATURE_WGET_HTTPS"
	func_disable_busybox_param "CONFIG_FEATURE_WGET_OPENSSL"
fi
''', 1)
        step("сделано", "configure: встроенный HTTPS в wget")

# 5c. в 1.38 swaponoff разделён на swapon и swapoff
if 'func_disable_busybox_param "CONFIG_SWAPOFF"' in s: step("уже есть", "configure: CONFIG_SWAPON/SWAPOFF рядом с SWAPONOFF")
else:
    s, n = re.subn(r'^(\t+)func_disable_busybox_param "CONFIG_SWAPONOFF"\n',
                   lambda m: m.group(0) + m.group(1) + 'func_disable_busybox_param "CONFIG_SWAPON"\n' + m.group(1) + 'func_disable_busybox_param "CONFIG_SWAPOFF"\n',
                   s, flags=re.M)
    step("сделано" if n else "НЕ НАЙДЕНО", "configure: CONFIG_SWAPON/SWAPOFF рядом с SWAPONOFF (%d мест)" % n)

if s != orig: wr(rel, s.replace("\n", "\r\n") if crlf else s)

# ================================================================ 6. профили плат: у всех плат BusyBox 1.38 (n возвращает 1.24.x)
tdir = os.path.join(N44, "trunk/configs/templates")
LINE = "CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y"
COMMENT = "### BusyBox 1.38 (user/busybox/Makefile.1.38); n or no line = old 1.24.x"
done = same = 0
for fn in sorted(os.listdir(tdir)):
    if not fn.endswith(".config"): continue
    p = os.path.join(tdir, fn); raw = rd(p); nl = "\r\n" if "\r\n" in raw else "\n"; s = raw.replace("\r\n", "\n")
    m = re.search(r"^[ \t]*#?[ \t]*CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=.*$", s, re.M)
    if m:
        if m.group(0).strip() == LINE: same += 1; continue
        s = s[:m.start()] + LINE + s[m.end():]
    else:
        m = (re.search(r"^CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=.*$", s, re.M) or re.search(r"^CONFIG_FIRMWARE_INCLUDE_OPENSSL_EXE=.*$", s, re.M))
        if m: s = s[:m.end()] + "\n" + COMMENT + "\n" + LINE + s[m.end():]
        else: s = s.rstrip("\n") + "\n" + COMMENT + "\n" + LINE + "\n"
    wr(p, s.replace("\n", nl)); done += 1
step("сделано" if done else "уже есть", "профили плат: %s (изменено %d, уже было %d)" % (LINE, done, same))

print("\nГотово. Полная пересборка busybox: rm -rf trunk/user/busybox/busybox-1.38.0 (или make -C trunk/user/busybox clean), затем make RM2100.")
