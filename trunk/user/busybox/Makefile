# ng-port: версия BusyBox выбирается флагом профиля CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y (иначе 1.24.x)
ifeq ($(CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138),y)
include Makefile.1.38
else
include Makefile.1.24
endif
