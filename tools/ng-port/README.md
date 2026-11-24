# ng-port: перенос функций padavan-ng на padavan-4.4 (ядро Linux 4.4.198)

Ветка `ng-port` форка padavan-4.4 добавляет из padavan-ng: клиент AmneziaWG (AWG 3.1), Zapret/Zapret2, сервисы
DoH / DoT (stubby) / DNSCrypt, OpenVPN, русский язык, меню «Сервисы». Проверено **только на Redmi AC2100 / RM2100 (MT7621)**.
Остальные платы сохранены, новые опции для них выключены (включаются заменой `n` на `y` в профиле платы).

## Что внутри
- `tools/ng-port/port-build-fixes.py` — идемпотентные правила 1–32, применяются к дереву; повторный запуск ничего не меняет.
- `tools/ng-port/port-dns-services.py` — перенос DoH, DoT, DNSCrypt, libgetdns, libyaml из padavan-ng.
- `tools/ng-port/awg-conf-import.sh` — (на роутере) переносит параметры AWG из `.conf` в nvram.
- `tools/ng-port/awg-debug.py`, `awg-sniff*`, `port-survey-*.sh` — отладка и обзор дерева.

## Сборка
Требуется чистая оболочка: **без `STAGEDIR` и без путей padavan-ng в `PATH`/окружении** (иначе пакеты, собираемые autoconf и
CMake, подхватывают чужие библиотеки: ошибки `libssl.so.3`, падение dnscrypt-proxy при старте).

```bash
unset STAGEDIR
cd ~/prometeus/update                                    # рядом лежат padavan-ng и padavan-4.4
python3 padavan-4.4/tools/ng-port/port-build-fixes.py padavan-4.4
python3 padavan-4.4/tools/ng-port/port-dns-services.py padavan-ng padavan-4.4
cd padavan-4.4 && make RM2100 2>&1 | tee build.log
```

Образ: `trunk/images/RM2100_4.4.198.9-100_<хеш>.trx` (хеш — 7 знаков коммита git; без git суффикса нет).

Перед пересборкой после смены окружения удалите каталоги сборки пакетов и файл `config_done` у затронутых пакетов
(libgetdns, stubby, doh_proxy, dnscrypt-proxy), иначе останутся старые настройки.

## Прошивка
Через веб-интерфейс («Администрирование» → «Обновление микропрограммы»); после записи роутер перезагружается сам.
После перепрошивки на ПК: `ssh-keygen -R 192.168.1.1`.

## Основные правила (кратко)
- 15: буфер nvram 1024 → NVRAM_MAX_VALUE_LEN (полные параметры I1 AWG).
- 16, 20: `update_resolvconf` и маршруты до публичных DNS через туннель AWG.
- 17: **.json отдаёт httpd (веб-импорт параметров AWG).
- 26: тихий лог HNAT (`mtk_pong_hqos_handler`).
- 29: `export STAGEDIR` для CMake. 30: перезагрузка после прошивки через `reboot(2)`.
- 31, 32: версия и имя образа с хешем git.

## Известные ограничения
- Сервис IPSet не перенесён (страница есть, backend нет); вкладка Service8 пустая, как в ng.
- Правило 25 (DNS туннеля) выключено по умолчанию (`NG_TUNNEL_DNS=1` включает). Адреса DNS в прошивку не зашиты: берутся из профиля AWG.
- DoH, DoT и DNSCrypt включайте по одному: dnsmasq работает в режиме `no-resolv` и при упавшем демоне остаётся без DNS.
