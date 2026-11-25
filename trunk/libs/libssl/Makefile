# https://openssl-library.org/source
# Версия выбирается в trunk/libs/Makefile (SSL_VER): 3.5 при CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=y, иначе 1.1.

all:
	$(MAKE) -C $(SSL_VER) all

%:
	$(MAKE) -C $(SSL_VER) $@

clean:
	( for i in 1.1 3.5; do \
		if [ -d $$i ]; then \
			$(MAKE) -C $$i clean; \
		fi; \
	done )

romfs:
	$(MAKE) -C $(SSL_VER) romfs
