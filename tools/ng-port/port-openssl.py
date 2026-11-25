#!/usr/bin/env python3
"""
Обновление OpenSSL в padavan-4.4 с 1.1.1w (снята с поддержки) до 3.5 LTS (3.5.9), как в padavan-ng.

Что делает (идемпотентно):
  * trunk/libs/libssl превращается в диспетчер версий, как в ng: 1.1/ (прежний пакет 1.1.1w без изменений) и
    3.5/ (Makefile под соглашения 4.4, патчи ng, openssl.cnf); тарболл 3.5.9 (53 МБ) в git не кладётся,
    он скачивается при сборке с github.com/openssl/openssl/releases и проверяется по SHA-256;
  * trunk/libs/Makefile: версия выбирается флагом CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=y (иначе 1.1);
  * профили плат: у всех плат CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=y (ранее выставленное n заменяется на y);
    платы без этой строки (свои профили) остаются на 1.1.1w, n в профиле тоже возвращает 1.1.1w;
  * wpa_supplicant 2.7: в OpenSSL 3.x нет MD4 (нужен для PEAP-MSCHAPv2), поэтому используется md4-internal.c
    из дерева wpa_supplicant (CONFIG_INTERNAL_MD4=y, md4_vector из crypto_openssl.c отключён).

  python3 port-openssl.py <путь_к_padavan-ng> <путь_к_padavan-4.4>

Проверено на хосте: патчи ng накладываются на 3.5.9, Configure для linux-mips32 с этими опциями проходит,
библиотека собирается; OpenVPN 2.5.10 и wpa_supplicant 2.7 (с правкой MD4) собираются и линкуются с 3.5.9.
После запуска нужна пересборка зависимых пакетов, см. README-ng-port.md (раздел OpenSSL 3.5).
"""
import os, re, shutil, sys

if len(sys.argv) < 3: print(__doc__); sys.exit(1)
NG, N44 = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
for d in (NG, N44):
    if not os.path.isdir(os.path.join(d, "trunk")): print("ОШИБКА: нет %s/trunk" % d); sys.exit(1)

SSL_NAME, SSL_SHA = "openssl-3.5.9", "603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a"

def step(status, name): print("%-13s %s" % (status, name))
def rd(p):
    with open(p, encoding="utf-8", errors="surrogateescape", newline="") as f: return f.read()
def wr(p, s):
    with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="") as f: f.write(s)

LIBSSL = os.path.join(N44, "trunk/libs/libssl")
NGSSL = os.path.join(NG, "trunk/libs/libssl")

# ================================================================ 1. libs/libssl/1.1 (прежний пакет)
d11 = os.path.join(LIBSSL, "1.1")
if os.path.exists(os.path.join(d11, "Makefile")):
    step("уже есть", "libs/libssl/1.1")
elif not os.path.exists(os.path.join(LIBSSL, "Makefile")) or "openssl-1.1.1w" not in rd(os.path.join(LIBSSL, "Makefile")):
    step("НЕ НАЙДЕНО", "libs/libssl/Makefile с openssl-1.1.1w (ожидался прежний пакет)")
else:
    os.makedirs(d11, exist_ok=True)
    for name in ("Makefile", "openssl-1.1.1w.patch", "openssl.cnf", "openssl-1.1.1w.tar.gz"):
        src = os.path.join(LIBSSL, name)
        if os.path.exists(src): shutil.move(src, os.path.join(d11, name))
    step("сделано", "libs/libssl: файлы 1.1.1w перенесены в 1.1/")

# ================================================================ 2. libs/libssl/3.5
d35 = os.path.join(LIBSSL, "3.5")
os.makedirs(d35, exist_ok=True)

MK35 = r'''# OpenSSL 3.5 LTS (https://openssl-library.org/source). Перенос из padavan-ng, соглашения 4.4 сохранены
# (--prefix=$(STAGEDIR), install_sw без DESTDIR), как в 1.1/Makefile.
SRC_NAME = %(name)s
SRC_URL = https://github.com/openssl/openssl/releases/download/$(SRC_NAME)/$(SRC_NAME).tar.gz
SRC_SHA256 = %(sha)s

# openssl use CROSS_COMPILE prefix
CC = gcc
AR = ar
RANLIB = ranlib
CXX = g++

COPTS = $(CPUFLAGS) -ffunction-sections -fdata-sections -Wl,--gc-sections
COPTS += $(if $(CONFIG_CC_OPTIMIZE_FOR_SIZE),-Os,-O3) $(filter-out -O%%, $(CFLAGS))
COPTS += $(if $(CONFIG_IPV6),-DOPENSSL_USE_IPV6=1,)
COPTS += -DOPENSSL_PREFER_CHACHA_OVER_GCM
COPTS += $(if $(CONFIG_CC_OPTIMIZE_FOR_SIZE),-DOPENSSL_SMALL_FOOTPRINT,)

CFLAGS := $(COPTS)
CXXFLAGS := $(COPTS)

# no-threads: как в 1.1 (так libssl не требует libatomic на mipsel)
OPENSSL_OPTIONS = no-capieng no-cms no-rfc3779 no-seed no-async no-ec2m \
                  no-err no-idea no-rc5 no-rmd160 no-blake2 no-static-engine \
                  no-md2 no-sse2 no-dso no-ts no-mdc2 no-cast no-whirlpool \
                  no-sctp no-srp no-ssl3 no-aria no-ssl3-method no-tests \
                  no-sm2 no-sm3 no-sm4 no-afalgeng no-comp disable-dynamic-engine \
                  no-quic no-threads

ifdef CONFIG_CRYPTO_DEV_LINUX
OPENSSL_OPTIONS += enable-devcryptoeng
else
OPENSSL_OPTIONS += no-devcryptoeng no-engine
endif

ifneq ($(CONFIG_FIRMWARE_INCLUDE_SSWAN),y)
OPENSSL_OPTIONS += no-rc2
endif

# без эллиптических кривых TLS 1.3 и современные серверы не работают: no-ec только если ни один пакет их не использует
ifeq (,$(filter y,$(CONFIG_FIRMWARE_INCLUDE_OPENSSL_EC) \
                  $(CONFIG_FIRMWARE_INCLUDE_OPENVPN) \
                  $(CONFIG_FIRMWARE_INCLUDE_DOH) \
                  $(CONFIG_FIRMWARE_INCLUDE_STUBBY) \
                  $(CONFIG_FIRMWARE_INCLUDE_CURL) \
                  $(CONFIG_FIRMWARE_INCLUDE_EAP_PEAP)))
OPENSSL_OPTIONS += no-ec
endif

all: download_test extract_test config_test
	$(MAKE) -j$(HOST_NCPU) -C $(SRC_NAME)

download_test:
	( if [ ! -f $(SRC_NAME).tar.gz ]; then \
		wget -t5 -T20 --no-check-certificate -O $(SRC_NAME).tar.gz $(SRC_URL) \
			|| rm -f $(SRC_NAME).tar.gz; \
	fi; \
	if [ -f $(SRC_NAME).tar.gz ] && [ "`sha256sum $(SRC_NAME).tar.gz | cut -d' ' -f1`" != "$(SRC_SHA256)" ]; then \
		echo "$(SRC_NAME).tar.gz: wrong SHA-256, removed"; \
		rm -f $(SRC_NAME).tar.gz; \
	fi; \
	[ -f $(SRC_NAME).tar.gz ] )

extract_test:
	( if [ ! -d $(SRC_NAME) ]; then \
		tar zxf $(SRC_NAME).tar.gz; \
		find "$(shell pwd)"/patches -type f -name "*.patch" -print0 \
		  | sort -z \
		  | xargs -r -t -0 -n 1 patch -d $(SRC_NAME) -p1 -i; \
	fi )

config_test:
	( if [ -f ./config_done ]; then \
		echo "the same configuration"; \
	else \
		make configure && touch config_done; \
	fi )

configure:
	( cd $(SRC_NAME); \
	./Configure \
		linux-mips32 \
		shared \
		--prefix=$(STAGEDIR) \
		--openssldir=/etc/ssl \
		$(OPENSSL_OPTIONS); \
	)

clean:
	[ ! -f $(SRC_NAME)/Makefile ] || $(MAKE) -C $(SRC_NAME) clean
	rm -f config_done

install:
	$(MAKE) -C $(SRC_NAME) install_sw DESTDIR=""
	$(MAKE) -C $(SRC_NAME) install_ssldirs DESTDIR="$(STAGEDIR)"
	rm -f $(DESTDIR)/lib/libssl.a
	rm -f $(DESTDIR)/lib/libcrypto.a

romfs:
	cp -fP $(DESTDIR)/lib/libssl.so* $(ROMFSDIR)/lib
	cp -fP $(DESTDIR)/lib/libcrypto.so* $(ROMFSDIR)/lib
	$(ROMFSINST) /etc_ro/openssl.cnf
ifeq ($(CONFIG_FIRMWARE_INCLUDE_OPENSSL_EXE),y)
	$(ROMFSINST) $(SRC_NAME)/apps/openssl /usr/bin/openssl
endif
''' % {"name": SSL_NAME, "sha": SSL_SHA}

mk35 = os.path.join(d35, "Makefile")
if os.path.exists(mk35) and rd(mk35) == MK35: step("уже есть", "libs/libssl/3.5/Makefile")
else: wr(mk35, MK35); step("сделано", "libs/libssl/3.5/Makefile (%s)" % SSL_NAME)

# патчи ng (накладываются и на 3.5.9)
pd_ng, pd44 = os.path.join(NGSSL, "3.5/patches"), os.path.join(d35, "patches")
if not os.path.isdir(pd_ng): step("НЕТ В NG", "libs/libssl/3.5/patches")
else:
    same = os.path.isdir(pd44) and sorted(os.listdir(pd44)) == sorted(os.listdir(pd_ng)) and \
        all(open(os.path.join(pd44, n), "rb").read() == open(os.path.join(pd_ng, n), "rb").read() for n in os.listdir(pd_ng))
    if same: step("уже есть", "libs/libssl/3.5/patches")
    else:
        shutil.rmtree(pd44, ignore_errors=True); shutil.copytree(pd_ng, pd44)
        step("сделано", "libs/libssl/3.5/patches (%d файлов из padavan-ng)" % len(os.listdir(pd44)))

# openssl.cnf: тот же файл, что в 1.1, плюс системные настройки TLS (как в ng, без раздела engine)
cnf11 = os.path.join(d11, "openssl.cnf")
CNF_TAIL = "\n[ default_conf ]\nssl_conf=ssl_sect\n\n[ssl_sect]\nsystem_default=system_default_sect\n\n[system_default_sect]\nMinProtocol=TLSv1.2\nCipherString=DEFAULT:@SECLEVEL=1\n"
cnf35 = os.path.join(d35, "openssl.cnf")
if not os.path.exists(cnf11): step("НЕ НАЙДЕНО", "libs/libssl/1.1/openssl.cnf")
else:
    base = rd(cnf11)
    nl = "\r\n" if "\r\n" in base else "\n"
    new = "openssl_conf\t\t= default_conf" + nl + base.lstrip("\r\n")
    new = new.rstrip("\r\n") + nl + CNF_TAIL.replace("\n", nl)
    if os.path.exists(cnf35) and rd(cnf35) == new: step("уже есть", "libs/libssl/3.5/openssl.cnf")
    else: wr(cnf35, new); step("сделано", "libs/libssl/3.5/openssl.cnf")

# ================================================================ 3. libs/libssl/Makefile — диспетчер версий
DISP = '''# https://openssl-library.org/source
# Версия выбирается в trunk/libs/Makefile (SSL_VER): 3.5 при CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=y, иначе 1.1.

all:
	$(MAKE) -C $(SSL_VER) all

%:
	$(MAKE) -C $(SSL_VER) $@

clean:
	( for i in 1.1 3.5; do \\
		if [ -d $$i ]; then \\
			$(MAKE) -C $$i clean; \\
		fi; \\
	done )

romfs:
	$(MAKE) -C $(SSL_VER) romfs
'''
dm = os.path.join(LIBSSL, "Makefile")
if os.path.exists(dm) and rd(dm) == DISP: step("уже есть", "libs/libssl/Makefile (диспетчер)")
else: wr(dm, DISP); step("сделано", "libs/libssl/Makefile (диспетчер версий)")

# ================================================================ 4. libs/Makefile: выбор SSL_VER
lm = os.path.join(N44, "trunk/libs/Makefile")
s = rd(lm); nl = "\r\n" if "\r\n" in s else "\n"
if "SSL_VER" in s: step("уже есть", "libs/Makefile: SSL_VER")
else:
    m = re.search(r"^dir_y\t+\+= libz[ \t]*\r?$", s, re.M)
    if not m: step("НЕ НАЙДЕНО", "libs/Makefile: якорь dir_y += libz")
    else:
        blk = ["ifeq ($(CONFIG_FIRMWARE_INCLUDE_OPENSSL_35),y)", "SSL_VER = 3.5", "else", "SSL_VER = 1.1", "endif", "", ""]
        wr(lm, s[:m.start()] + nl.join(blk) + s[m.start():]); step("сделано", "libs/Makefile: SSL_VER (3.5 при OPENSSL_35=y, иначе 1.1)")

# ================================================================ 5. профили плат
tdir = os.path.join(N44, "trunk/configs/templates")
for fn in sorted(os.listdir(tdir)):
    if not fn.endswith(".config"): continue
    p = os.path.join(tdir, fn); s = rd(p); nl = "\r\n" if "\r\n" in s else "\n"
    val = "y"
    line = "CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=" + val
    m = re.search(r"^[ \t]*#?[ \t]*CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=.*$", s, re.M)
    if m:
        if m.group(0).strip() == line: continue
        wr(p, s[:m.start()] + line + s[m.end():]); step("сделано", "%s: %s" % (fn, line)); continue
    m = re.search(r"^CONFIG_FIRMWARE_INCLUDE_OPENSSL_EXE=.*\r?$", s, re.M)
    if not m: step("НЕ НАЙДЕНО", "%s: якорь CONFIG_FIRMWARE_INCLUDE_OPENSSL_EXE" % fn); continue
    ins = nl + "### Use OpenSSL 3.5 LTS (libs/libssl/3.5) instead of 1.1.1w (end of life); n = back to 1.1.1w" + nl + line
    wr(p, s[:m.end()] + ins + s[m.end():]); step("сделано", "%s: %s" % (fn, line))
step("проверено", "профили плат (OPENSSL_35=y у всех)")

# ================================================================ 6. wpa_supplicant: внутренний MD4 (в OpenSSL 3.x MD4 нет в провайдере по умолчанию)
wd = os.path.join(N44, "trunk/user/wpa_supplicant")
cp = os.path.join(wd, "src/crypto/crypto_openssl.c")
if os.path.exists(cp):
    s = rd(cp); nl = "\r\n" if "\r\n" in s else "\n"
    old = nl.join(["int md4_vector(size_t num_elem, const u8 *addr[], const size_t *len, u8 *mac)", "{",
                   "\treturn openssl_digest_vector(EVP_md4(), num_elem, addr, len, mac);", "}"])
    if "ng-port: OpenSSL 3.x" in s: step("уже есть", "wpa_supplicant: crypto_openssl.c без md4_vector")
    elif s.count(old) != 1: step("НЕ НАЙДЕНО", "wpa_supplicant: md4_vector в crypto_openssl.c")
    else:
        new = nl.join(["#if 0 /* ng-port: OpenSSL 3.x default provider has no MD4; md4-internal.c is used (CONFIG_INTERNAL_MD4) */", old, "#endif /* ng-port */"])
        wr(cp, s.replace(old, new)); step("сделано", "wpa_supplicant: md4_vector из crypto_openssl.c отключён")
else: step("НЕТ ФАЙЛА", "wpa_supplicant/src/crypto/crypto_openssl.c")
wm = os.path.join(wd, "Makefile")
if os.path.exists(wm):
    s = rd(wm); nl = "\r\n" if "\r\n" in s else "\n"
    if "CONFIG_INTERNAL_MD4" in s: step("уже есть", "wpa_supplicant/Makefile: CONFIG_INTERNAL_MD4")
    else:
        anchor = "\tcp -f $(SRC_NAME)/.config.def $(SRC_NAME)/.config" + nl
        if anchor not in s: step("НЕ НАЙДЕНО", "wpa_supplicant/Makefile: якорь cp .config.def")
        else:
            wr(wm, s.replace(anchor, anchor + "\techo CONFIG_INTERNAL_MD4=y >> $(SRC_NAME)/.config" + nl, 1))
            step("сделано", "wpa_supplicant/Makefile: CONFIG_INTERNAL_MD4=y")

print("\nГотово. Дальше: пересборка с очисткой зависимых пакетов (см. README-ng-port.md, раздел OpenSSL 3.5).")
