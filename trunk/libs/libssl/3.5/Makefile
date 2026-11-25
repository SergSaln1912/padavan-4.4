# OpenSSL 3.5 LTS (https://openssl-library.org/source). Перенос из padavan-ng, соглашения 4.4 сохранены
# (--prefix=$(STAGEDIR), install_sw без DESTDIR), как в 1.1/Makefile.
SRC_NAME = openssl-3.5.9
SRC_URL = https://github.com/openssl/openssl/releases/download/$(SRC_NAME)/$(SRC_NAME).tar.gz
SRC_SHA256 = 603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a

# openssl use CROSS_COMPILE prefix
CC = gcc
AR = ar
RANLIB = ranlib
CXX = g++

COPTS = $(CPUFLAGS) -ffunction-sections -fdata-sections -Wl,--gc-sections
COPTS += $(if $(CONFIG_CC_OPTIMIZE_FOR_SIZE),-Os,-O3) $(filter-out -O%, $(CFLAGS))
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
