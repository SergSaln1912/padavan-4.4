# ng-port: padavan-ng features on padavan-4.4 (Linux 4.4.198)

English | [Русский](README.ru.md)

The `ng-port` branch of this fork brings features from [padavan-ng](https://github.com/nilabsent/padavan-ng) to
[padavan-4.4](https://github.com/vb1980/padavan-4.4): the AmneziaWG client (AWG 3.1), Zapret / Zapret2, DNS services
(DoH, DoT via stubby, DNSCrypt), IPSet service, OpenVPN, Russian language, the "Services" menu, dnsmasq 2.93 with regex,
and OpenSSL 3.5 LTS.

**Verified only on Redmi AC2100 / RM2100 (MT7621).** Other boards keep their profiles; new options are present in their
profiles too, but those boards were not built or tested. Options that are off by default can be switched on by replacing
`n` with `y` in the board profile (`trunk/configs/templates/<BOARD>.config`).

## What is in `tools/ng-port`
All scripts are idempotent: a second run changes nothing. They take the two trees as arguments:
`python3 <script> <path-to-padavan-ng> <path-to-padavan-4.4>` (only `port-build-fixes.py` takes just the 4.4 tree).

| File | Purpose |
|---|---|
| `port-build-fixes.py` | Rules 1–34 applied to the tree (AWG, DNS, nvram buffer, HNAT log, reboot after flashing, version with git hash, board profile flags). |
| `port-dns-services.py` | DoH (https_dns_proxy), DoT (stubby + libgetdns), DNSCrypt, libyaml: packages, rc, httpd, pages, dictionaries. |
| `port-dnsmasq.py` + `210-max-procs-4.patch` | dnsmasq 2.90 → 2.93 with the ng regex patches (needs libpcre). |
| `port-ipset.py` | IPSet service: `ipset.sh`, "IPSet" tab, `dnsmasq.ipset` editor, update timer. |
| `port-openssl.py` | OpenSSL 1.1.1w → 3.5.9 LTS (`libs/libssl/{1.1,3.5}`), internal MD4 for wpa_supplicant. |
| `port-busybox.py` | BusyBox 1.24.x → 1.38.0 (flag `CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138`, ng patches and config); all boards. |
| `awg-conf-import.sh` | (on the router) imports AWG parameters from a `.conf` into nvram. |
| `awg-debug.py`, `awg-sniff*`, `port-survey-*.sh` | Debugging and tree survey helpers. |

## Build
The shell must be clean: **no `STAGEDIR` and no padavan-ng paths in `PATH` or the environment**. Otherwise autoconf and
CMake packages pick up foreign libraries (`libssl.so.3` errors, dnscrypt-proxy crashing at start).

```bash
unset STAGEDIR
cd ~/prometeus/update                                    # padavan-ng and padavan-4.4 side by side
python3 padavan-4.4/tools/ng-port/port-build-fixes.py padavan-4.4
python3 padavan-4.4/tools/ng-port/port-dns-services.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-dnsmasq.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-ipset.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-openssl.py padavan-ng padavan-4.4
python3 padavan-4.4/tools/ng-port/port-busybox.py padavan-ng padavan-4.4
cd padavan-4.4 && make RM2100 2>&1 | tee build.log
```

The image is `trunk/images/RM2100_4.4.198.9-100_<hash>.trx` (the hash is the 7-character git commit; without git there is
no suffix). After switching environments, remove the build directories and `config_done` of the affected packages
(libgetdns, stubby, doh_proxy, dnscrypt-proxy), otherwise old settings remain.

### One-time cleanup when moving to OpenSSL 3.5
`libs/Makefile` installs libraries into `stage` once (markers `stage/.installed_<package>`), so without cleanup the
OpenSSL 1.1.1 headers and libraries stay in `stage` and dependent packages are not rebuilt.

```bash
cd ~/prometeus/update/padavan-4.4/trunk
rm -f stage/.installed_libssl stage/.installed_libcurl stage/.installed_libgetdns
rm -rf stage/include/openssl stage/lib/libssl* stage/lib/libcrypto* stage/lib/pkgconfig/{openssl,libssl,libcrypto}.pc
for d in libs/libssl libs/libcurl libs/libgetdns user/stubby user/doh_proxy user/openvpn user/inadyn user/wpa_supplicant; do
    make -C $d clean 2>/dev/null; rm -f $d/config_done
done
cd .. && make RM2100 2>&1 | tee build.log
```
After the build, `readelf -d` of `stubby`, `https_dns_proxy`, `openvpn`, `wpa_supplicant` and `curl` must show
`libssl.so.3` / `libcrypto.so.3` (not `.1.1`), and no `padavan-ng` path may appear in any `config.log` / `CMakeCache.txt`.

## OpenSSL 3.5
`port-openssl.py` moves all boards to OpenSSL 3.5.9 (LTS until 2030-04-08). The 53 MB tarball is not stored in git: it
is downloaded at build time from github.com/openssl/openssl/releases and checked against its SHA-256. The old package
is kept in `libs/libssl/1.1`; a board with `CONFIG_FIRMWARE_INCLUDE_OPENSSL_35=n` (or without the line) builds as before.

OpenSSL consumers in the RM2100 profile: libcurl 8.15 (curl, https_dns_proxy), OpenVPN 2.5.10, inadyn 2.12,
getdns/stubby 1.7.3, wpa_supplicant 2.7 (EAP-PEAP).

Behaviour changes:
- `openssl.cnf`: `MinProtocol=TLSv1.2`, `CipherString=DEFAULT:@SECLEVEL=1` (as in ng). Servers that only speak TLS 1.0/1.1
  (old RADIUS servers for EAP, old HTTPS sites) stop working.
- OpenSSL 3 has no MD4, RC2 or Blowfish in the default provider (there is no legacy provider in this build).
  wpa_supplicant uses its own MD4 (patch in `port-openssl.py`); OpenVPN profiles with `cipher BF-CBC` stop working, use AES.
- The image grows (libcrypto 3.x is larger than 1.1.1).
- The `openssl` executable stays in the RM2100 image (rule 33): `openvpn-cert.sh`, `https-cert.sh` and `aliddns.sh` need it.

## BusyBox 1.38
`port-busybox.py` adds BusyBox 1.38.0 next to the old 1.24.x: `trunk/user/busybox/Makefile` picks the version by the profile flag
`CONFIG_FIRMWARE_INCLUDE_BUSYBOX_138=y` (set for all boards; without the flag or with `n` 1.24.x is built; only RM2100 was built and tested).
The tarball (2.7 MB) is downloaded from busybox.net at build time and checked against SHA-256 (the sum comes from the tarball in
padavan-ng); the patches (`dhcp6c`, `udhcpc`, `ntpd`, `syslogd`, `init`, ...) and the config (`configs/boards/busybox-1.38.config`)
come from ng. `wget` does https with BusyBox's built-in TLS, the `openssl` program is not needed for that.

Missing from the ng config compared with 1.24.x: ash `getopts`, `base64`, `getopt`, `groups`, `hexdump`, `id`, `modinfo`, `nohup`,
`sha256sum`, `telnet`, `unzip` (firmware scripts do not call them; enable in `busybox-1.38.config` if needed).
Verified on the host: patches apply, the config resolves without questions, BusyBox builds, 227 firmware scripts pass `sh -n` with the
new ash. Verified on the router (RM2100, `bb-check.sh`): boot, WAN DHCP (`udhcpc`), `dhcp6c`, NTP, `wget` over https with the built-in TLS, `nc -u`,
`sysctl vm.drop_caches`, `syslogd`, 41 scripts pass `sh -n`. Other boards were not built. If the router does not boot, set `n` in the
profile and rebuild (or flash the previous image). `bb-check.sh` is the post-flash check script.

## Flashing
Through the web interface ("Administration" → "Firmware update"); the router reboots itself after writing (rule 30).
After flashing, on the PC: `ssh-keygen -R 192.168.1.1`.

## Key rules (short)
- 15: nvram buffer 1024 → `NVRAM_MAX_VALUE_LEN` (full AWG `I1` parameter).
- 16, 20: `update_resolvconf` and routes to public DNS through the AWG tunnel.
- 17: httpd serves `**.json` (web import of AWG parameters).
- 26: quiet HNAT log (`mtk_pong_hqos_handler`).
- 29: `export STAGEDIR` for CMake. 30: reboot after flashing via `reboot(2)`.
- 31, 32: firmware version and image name with the git hash. 33: `openssl` executable included in the RM2100 image.
- 34: web UI footer: "2011-2026" and a GitHub link (`GH_NICK` in the rule).

## IPSet service
- Enable with `ipset_enable` on the "IPSet" tab (off by default). Lists from `ipset.json` and `ipset_post_script.sh` are
  downloaded with **curl** (the busybox 1.24 `wget` cannot do HTTPS and returns 0 without writing a file).
- Regex entries in `dnsmasq.ipset` work when `CONFIG_FIRMWARE_ENABLE_DNSMASQ_REGEX=y` (RM2100); without it the image uses
  `ipset/dnsmasq.ipset.noregex`. For regex-matched domains dnsmasq adds addresses only from upstream answers, not from cache.
- Defaults under `/etc/storage/ipset/` are created only if missing: after an update delete a stale
  `ipset_post_script.sh` on the router and reboot.
- `Service8` tab is empty, as in ng.

## Known limitations
- Rule 25 (tunnel DNS) is off by default (`NG_TUNNEL_DNS=1` enables it). DNS addresses are not hard-coded: they come from the AWG profile.
- Enable DoH, DoT and DNSCrypt one at a time: dnsmasq runs with `no-resolv`, so a crashed daemon leaves it without DNS.
- Tor is not ported. `vpnc_ipset_allowed/exclude` have no defaults.
- Not verified on the router with OpenSSL 3.5: OpenVPN and certificate generation, wpa_supplicant (EAP-PEAP).

## Verified on RM2100
Redmi AC2100, image `4.4.198.9-100`: AmneziaWG (list mode), Zapret2, DoH, DoT (stubby answers on 127.0.0.1:5453) and DNSCrypt (answers on 127.0.0.1:65053), dnsmasq 2.93 with regex and
ipset, IPSet service (update button and set pickers on the VPN client, Zapret and Proxy pages; 20 lists from `ipset.json` and 31 CDN lists from `ipset_post_script.sh` load at boot),
OpenSSL 3.5.9 in `https_dns_proxy` / libcurl, reboot after flashing, BusyBox 1.38.0.

---

## Upstream README (vb1980/padavan-4.4)

This project is based on original rt-n56u with latest mtk 4.4.198 kernel, which is fetch from D-LINK GPL code.

###### Enhancements in this repo

- commits has beed rewritten on top of [hanwckf/rt-n56u](https://github.com/hanwckf/rt-n56u) repo for better history tracking
- Optimized Makefiles and build scripts, added a toplevel Makefile
- Added ccache support, may save up to 50%+ build time
- Upgraded the toolchain and libc:
  - gcc 10.3.0
  - uClibc-ng 1.0.47
 - Enabled kernel cgroups support
 - Fixed K2P led label names
 - Replaced udpxy with msd_lite
 - Replaced Web Console with ttyd
 - Upgraded libs and user packages
 - And a lot of package related fixes
 - ...

## Features

- Based on 4.4.198 Linux kernel
- Support MT7621 based devices
- Support MT7615D/MT7615N/MT7915D wireless chips
- Support raeth and mt7621 hwnat with legency driver
- Support qca shortcut-fe
- Support IPv6 NAT based on netfilter
- Support WireGuard integrated in kernel
- Support fullcone NAT (by Chion82)
- Support LED&GPIO control via sysfs

## Supported devices

- CR660x
- JCG-Q20
- JCG-AC860M
- JCG-836PRO
- JCG-Y2
- DIR-878
- DIR-882
- K2P
- K2P-USB
- NETGEAR-BZV
- MR2600
- MI-4
- MI-R3G
- MI-R3P
- R2100
- RM2100 (Redmi AC2100, MT7621; ng-port branch, tested: AmneziaWG, Zapret2, DoH/DoT/DNSCrypt, IPSet, OpenSSL 3.5, BusyBox 1.38)
- XY-C1
- GHL(from https://github.com/fangenhui520/padavan-4.4, 没有机器测试，自行判断)
- EA7500(from https://github.com/MNM28/padavan-4.4, 没有机器测试，自行判断)
- R6800(from https://github.com/MNM28/padavan-4.4, 没有机器测试，自行判断)
- TX1801 Plus(from https://github.com/MNM28/padavan-4.4, 没有机器测试，自行判断)
- JDCloud RE-CP-02(无线宝鲁班, from https://github.com/240038901/padavan-4.4, 没有机器测试，自行判断)
- JDCloud RE-SP-01B(from https://github.com/MeIsReallyBa/padavan-4.4, 没有机器测试，自行判断)
- NEWIFI3(from https://github.com/GH-X/padavan-4.4, 必须拆除主板上编号为C48的电容(位于CPU旁边), 否则外网(WAN)将不能正常工作)
- MI-R4A(from https://github.com/vipshmily/padavan-4.4, 没有机器测试，自行判断)
- QM-B1(from https://github.com/monw/padavan, 没有机器测试，自行判断)
- WE410443-TC(from https://github.com/akw28888/padavan-4.4, 没有机器测试，自行判断)
- HAR-20S2U1(from https://github.com/vb1980/padavan-4.4, 没有机器测试，自行判断)
- SIM-AX1800T(from https://github.com/vb1980/padavan-4.4, 自测可用)
- G-AX1800(富春江G-AX1800, from https://github.com/ddyjyj/padavan-4.4, 自测可用)
- G-AX1800-B(富春江G-AX1800黑色版本, 网口配置和白色版不一样，4根天线都是ipex可拆，ttl排针焊接好了，做工比白色版好些， from https://github.com/vb1980/padavan-4.4, 自测可用)
- WIA3300-10(西加云杉WIA3300-10，据说和K2P配置差不多，from https://github.com/vb1980/padavan-4.4, 自测可用)
- JCQ-Q11Pro(from https://github.com/qewwqewq22/padavan11, 没有机器测试，自行判断)
- R7450(from https://github.com/vipshmily/padavan-4.4, 没有机器测试，自行判断)
- 360-T6M(from https://github.com/BINGHUAice/padavan-4.4, 没有机器测试，自定判断)
- C-Life XG1(刷机简单，使用R3G分区，r3g breed刷入，from https://github.com/vb1980/padavan-4.4, 自测可用)
- ZTT-RX6000(中天科技RX6000的Wifi6运营商机器，ttl刷机简单，使用R3G分区，r3g breed刷入，from https://github.com/vb1980/padavan-4.4，自测可用)
- MAIPU-MPAX18(迈普MPAX18的Wifi6运营商机器，ttl刷机简单，使用R3G分区，r3g breed刷入，from https://github.com/vb1980/padavan-4.4，自测可用)
## Compilation steps

- Install dependencies
  ```sh
  # Debian/Ubuntu
  sudo apt install unzip libtool-bin ccache curl cmake gperf gawk flex bison nano xxd \
      fakeroot kmod cpio git python3-docutils gettext automake autopoint \
      texinfo build-essential help2man pkg-config zlib1g-dev libgmp3-dev \
      libmpc-dev libmpfr-dev libncurses5-dev libltdl-dev wget libc-dev-bin
  ```
  **Optional:** install [golang](https://go.dev/doc/install) (and add it to PATH), if you are going to build go programs
- Clone source code
  ```sh
  git clone https://github.com/vb1980/padavan-4.4.git
  ```
- Modify template file and start compiling
  ```sh
  # (Optional) Modify template file
  # vi trunk/configs/templates/K2P.config

  # Start compiling with: make PRODUCT_NAME
  make K2P

  # To build firmware for other devices, clean the tree after previous build
  make clean
  ```

## Package Development

- Makefile examples
  - [Makefile project](trunk/libs/libpcre/Makefile) 
  - [CMake project](trunk/user/ttyd/Makefile)
- Compiling a single package (cd to `trunk` first)
  - build: `make libs/libpcre_only`
  - clean: `make libs/libpcre_clean`
  - romfs: `make libs/libpcre_romfs`

## Manuals

- Controlling GPIO and LEDs via sysfs
- How to use NAND RWFS partition
- How to use IPv6 NAT and fullcone NAT
- How to add new device support with device tree
