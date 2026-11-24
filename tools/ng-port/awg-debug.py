#!/usr/bin/env python3
"""
Включает/выключает отладку модуля AmneziaWG (-DDEBUG: самотесты шифрования и сообщения в dmesg).
  python3 awg-debug.py <путь_к_padavan-4.4> on|off
После "on" пересоберите прошивку (make RM2100), прошейте и смотрите dmesg | grep -i amnezia.
"""
import os, sys
if len(sys.argv) < 3 or sys.argv[2] not in ("on", "off"): print(__doc__); sys.exit(1)
p = os.path.join(os.path.abspath(sys.argv[1]), "trunk/linux-4.4.x/net/amneziawg/Kbuild")
if not os.path.exists(p): print("НЕТ ФАЙЛА", p); sys.exit(1)
s = open(p, encoding="utf-8", errors="surrogateescape", newline="").read()
orig = "ccflags-$(CONFIG_AMNEZIAWG_DEBUG) += -DDEBUG -g"
dbg  = "ccflags-y += -DDEBUG -g # ng-port debug"
if sys.argv[2] == "on":
    if dbg in s: print("уже включено")
    elif orig in s: open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s.replace(orig, dbg, 1)); print("отладка AmneziaWG ВКЛЮЧЕНА")
    else: print("НЕ НАЙДЕНО: строка с CONFIG_AMNEZIAWG_DEBUG")
else:
    if orig in s and dbg not in s: print("уже выключено")
    elif dbg in s: open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s.replace(dbg, orig, 1)); print("отладка AmneziaWG ВЫКЛЮЧЕНА")
    else: print("НЕ НАЙДЕНО: строка отладки")
