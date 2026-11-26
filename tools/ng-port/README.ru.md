# ng-port: функции padavan-ng на padavan-4.4 (ядро Linux 4.4.198)

[English](README.md) | Русский

Ветка `ng-port` этого форка переносит из [padavan-ng](https://github.com/nilabsent/padavan-ng) в
[padavan-4.4](https://github.com/vb1980/padavan-4.4): клиент AmneziaWG (AWG 3.1), Zapret / Zapret2, DNS-сервисы
(DoH, DoT через stubby, DNSCrypt), сервис IPSet, OpenVPN, русский язык, меню «Сервисы», dnsmasq 2.93 с regex
и OpenSSL 3.5 LTS.

**Проверено только на Redmi AC2100 / RM2100 (MT7621).** Остальные платы сохранены, новые опции есть и в их профилях,
но эти платы не собирались и не проверялись. Выключенные по умолчанию опции включаются заменой `n` на `y`
в профиле платы (`trunk/configs/templates/<ПЛАТА>.config`).

## Что в `tools/ng-port`
Все скрипты идемпотентны: повторный запуск ничего не меняет. Аргументы — два дерева:
`python3 <скрипт> <путь_к_padavan-ng> <путь_к_padavan-4.4>` (только `port-build-fixes.py` принимает одно дерево 4.4).

| Файл | Назначение |
|---|---|
| `port-build-fixes.py` | Правила 1–34 (AWG, DNS, буфер nvram, лог HNAT, перезагрузка после прошивки, версия с хешем git, флаги профилей плат). |
| `port-dns-services.py` | DoH (https_dns_proxy), DoT (stubby + libgetdns), DNSCrypt, libyaml: пакеты, rc, httpd, страницы, словари. |
| `port-dnsmasq.py` + `210-max-procs-4.patch` | dnsmasq 2.90 → 2.93 с regex-патчами ng (нужен libpcre). |
| `port-ipset.py` | Сервис IPSet: `ipset.sh`, вкладка «IPSet», редактор `dnsmasq.ipset`, обновление по таймеру. |
| `port-openssl.py` | OpenSSL 1.1.1w → 3.5.9 LTS (`libs/libssl/{1.1,3.5}`), внутренний MD4 для wpa_supplicant. |
| `port-busybox.py` | BusyBox 1.24.x → 1.38.0 (флаг `CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138`, патчи и конфиг ng); все платы. |
| `awg-conf-import.sh` | (на роутере) переносит параметры AWG из `.conf` в nvram. |
| `awg-debug.py`, `awg-sniff*`, `port-survey-*.sh` | Отладка и обзор дерева. |

## Сборка
Нужна чистая оболочка: **без `STAGEDIR` и без путей padavan-ng в `PATH`/окружении**. Иначе пакеты на autoconf и CMake
подхватывают чужие библиотеки (ошибки `libssl.so.3`, падение dnscrypt-proxy при старте).

```bash
unset STAGEDIR
cd ~/prometeus/update                                    # рядом лежат padavan-ng и padavan-4.4
python3 padavan-4.4/tools/ng-port/port-build-fixes.py padavan-4.4
python3 padavan-4.4/tools/ng-port/port-dns-services.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-dnsmasq.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-ipset.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-openssl.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-busybox.py padavan-ng padavan-4.4
cd padavan-4.4 && make RM2100 2>&1 | tee build.log
```

Образ: `trunk/images/RM2100_4.4.198.9-100_<хеш>.trx` (хеш — 7 знаков коммита git; без git суффикса нет).
После смены окружения удалите каталоги сборки и `config_done` у затронутых пакетов
(libgetdns, stubby, doh_proxy, dnscrypt-proxy), иначе останутся старые настройки.

### Однократная очистка при переходе на OpenSSL 3.5
`libs/Makefile` ставит библиотеки в `stage` один раз (метки `stage/.installed_<пакет>`), поэтому без очистки в `stage`
останутся заголовки и библиотеки OpenSSL 1.1.1, а зависимые пакеты не пересоберутся.

```bash
cd ~/prometeus/update/padavan-4.4/trunk
rm -f stage/.installed_libssl stage/.installed_libcurl stage/.installed_libgetdns
rm -rf stage/include/openssl stage/lib/libssl* stage/lib/libcrypto* stage/lib/pkgconfig/{openssl,libssl,libcrypto}.pc
for d in libs/libssl libs/libcurl libs/libgetdns user/stubby user/doh_proxy user/openvpn user/inadyn user/wpa_supplicant; do
    make -C $d clean 2>/dev/null; rm -f $d/config_done
done
cd .. && make RM2100 2>&1 | tee build.log
```
После сборки в `readelf -d` у `stubby`, `https_dns_proxy`, `openvpn`, `wpa_supplicant` и `curl` должны быть
`libssl.so.3` / `libcrypto.so.3` (не `.1.1`), а в `config.log` / `CMakeCache.txt` — ни одного пути `padavan-ng`.

## OpenSSL 3.5
`port-openssl.py` переводит все платы на OpenSSL 3.5.9 (LTS до 08.04.2030). Тарболл (53 МБ) в git не кладётся: при сборке
он скачивается с github.com/openssl/openssl/releases и проверяется по SHA-256. Прежний пакет лежит в `libs/libssl/1.1`;
плата с `CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=n` (или без этой строки) собирается как раньше.

Потребители OpenSSL в профиле RM2100: libcurl 8.15 (curl, https_dns_proxy), OpenVPN 2.5.10, inadyn 2.12,
getdns/stubby 1.7.3, wpa_supplicant 2.7 (EAP-PEAP).

Что меняется в работе:
- `openssl.cnf`: `MinProtocol=TLSv1.2`, `CipherString=DEFAULT:@SECLEVEL=1` (как в ng). Серверы, говорящие только TLS 1.0/1.1
  (старые RADIUS для EAP, старые https-сайты), перестанут работать.
- В OpenSSL 3 нет MD4, RC2 и Blowfish в провайдере по умолчанию (legacy-провайдера в этой сборке нет).
  wpa_supplicant использует собственный MD4 (правка в `port-openssl.py`); профили OpenVPN с `cipher BF-CBC` не заработают, нужен AES.
- Образ вырастет (libcrypto 3.x больше 1.1.1).
- Программа `openssl` остаётся в образе RM2100 (правило 33): она нужна `openvpn-cert.sh`, `https-cert.sh` и `aliddns.sh`.

## BusyBox 1.38
`port-busybox.py` добавляет BusyBox 1.38.0 рядом с прежним 1.24.x: `trunk/user/busybox/Makefile` выбирает версию по флагу
`CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y` в профиле (включён у всех плат; без флага или с `n` собирается 1.24.x; собирался и проверялся только RM2100).
Тарболл (2,7 МБ) скачивается при сборке с busybox.net и проверяется по SHA-256 (сумма взята из тарболла в padavan-ng),
патчи (`dhcp6c`, `udhcpc`, `ntpd`, `syslogd`, `init` и др.) и конфиг (`configs/boards/busybox-1.38.config`) взяты из ng.
`wget` по https работает встроенным TLS BusyBox, программа `openssl` для этого не нужна.

Чего нет в конфиге ng по сравнению с 1.24.x: `getopts` в ash, `base64`, `getopt`, `groups`, `hexdump`, `id`, `modinfo`, `nohup`,
`sha256sum`, `telnet`, `unzip` (скрипты прошивки их не вызывают; при необходимости включаются в `busybox-1.38.config`).
Проверено на хосте: патчи накладываются, конфиг разрешается без вопросов, BusyBox собирается, 227 скриптов прошивки проходят
`sh -n` новым ash. На роутере (RM2100, `bb-check.sh`): загрузка, DHCP WAN (`udhcpc`), `dhcp6c`, NTP, `wget` по https встроенным TLS, `nc -u`,
`sysctl vm.drop_caches`, `syslogd`, 41 скрипт `sh -n` — всё работает. Другие платы не собирались. Если роутер не грузится,
верните `n` в профиле и пересоберите (или прошейте прежний образ). `bb-check.sh` — скрипт проверки после прошивки.

## Прошивка
Через веб-интерфейс («Администрирование» → «Обновление микропрограммы»); после записи роутер перезагружается сам (правило 30).
После перепрошивки на ПК: `ssh-keygen -R 192.168.1.1`.

## Основные правила (кратко)
- 15: буфер nvram 1024 → `NVRAM_MAX_VALUE_LEN` (полный параметр `I1` AWG).
- 16, 20: `update_resolvconf` и маршруты до публичных DNS через туннель AWG.
- 17: httpd отдаёт `**.json` (веб-импорт параметров AWG).
- 26: тихий лог HNAT (`mtk_pong_hqos_handler`).
- 29: `export STAGEDIR` для CMake. 30: перезагрузка после прошивки через `reboot(2)`.
- 31, 32: версия и имя образа с хешем git. 33: программа `openssl` включена в образ RM2100.
- 34: подвал веб-интерфейса: «2011-2026» и ссылка на GitHub (`GH_NICK` в правиле).

## Сервис IPSet
- Включается переменной `ipset_enable` на вкладке «IPSet» (по умолчанию выключен). Списки из `ipset.json` и
  `ipset_post_script.sh` качаются через **curl** (`wget` из busybox 1.24 не умеет https и возвращает 0 без файла).
- Regex-записи в `dnsmasq.ipset` работают при `CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX=y` (RM2100); без него в образ ставится
  `ipset/dnsmasq.ipset.noregex`. Для доменов, совпавших по regex, dnsmasq добавляет адреса только из ответов вышестоящего
  сервера, а не из кэша.
- Файлы по умолчанию в `/etc/storage/ipset/` создаются только если их нет: после обновления удалите на роутере старый
  `ipset_post_script.sh` и перезагрузитесь.
- Вкладка Service8 пустая, как в ng.

## Известные ограничения
- Правило 25 (DNS туннеля) выключено по умолчанию (`NG_TUNNEL_DNS=1` включает). Адреса DNS в прошивку не зашиты: берутся из профиля AWG.
- DoH, DoT и DNSCrypt включайте по одному: dnsmasq работает в режиме `no-resolv`, и при упавшем демоне остаётся без DNS.
- Tor не перенесён. У `vpnc_ipset_allowed/exclude` нет значений по умолчанию.
- На роутере с OpenSSL 3.5 не проверено: OpenVPN и генерация сертификатов, wpa_supplicant (EAP-PEAP).

## Проверено на RM2100
Redmi AC2100, образ `4.4.198.9-100`: AmneziaWG (режим по списку), Zapret2, DoH, DoT (ответ stubby на 127.0.0.1:5453) и DNSCrypt (ответ на 127.0.0.1:65053), dnsmasq 2.93 с regex и ipset,
сервис IPSet (кнопка «Обновить» и выбор наборов на страницах VPN-клиента, Zapret и Proxy; при загрузке подгружаются 20 списков из `ipset.json` и 31 список CDN из `ipset_post_script.sh`),
OpenSSL 3.5.9 в `https_dns_proxy` / libcurl, перезагрузка после прошивки, BusyBox 1.38.0.

