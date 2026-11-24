/* awg-sniff: AF_PACKET-сниффер UDP-пакетов к/от одного IPv4-адреса (для роутера без tcpdump).
 * Использование: awg-sniff <интерфейс> <ip> <секунд> [-v]
 *   без -v: первые 60 пакетов подробно + сводка раз в секунду; с -v: все пакеты подробно.
 * Поле "wg=" это тип сообщения WireGuard в первых 4 байтах (1 инициация, 2 ответ, 3 cookie, 4 данные).
 * Для исходящих пакетов "csum=BAD" может быть нормой: контрольную сумму дополняет сетевая карта после отправки.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdint.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <linux/if_packet.h>
#include <linux/if_ether.h>

static uint32_t csum_add(uint32_t s, const uint8_t *p, int n)
{
	while (n > 1) { s += (p[0] << 8) | p[1]; p += 2; n -= 2; }
	if (n) s += p[0] << 8;
	return s;
}

static double now_ms(void)
{
	struct timeval tv; gettimeofday(&tv, NULL);
	return tv.tv_sec * 1000.0 + tv.tv_usec / 1000.0;
}

int main(int argc, char **argv)
{
	if (argc < 4) { fprintf(stderr, "использование: %s <интерфейс> <ip> <секунд> [-v]\n", argv[0]); return 1; }
	const char *ifname = argv[1];
	struct in_addr want; if (!inet_aton(argv[2], &want)) { fprintf(stderr, "плохой ip\n"); return 1; }
	int secs = atoi(argv[3]);
	int verbose = argc > 4 && !strcmp(argv[4], "-v");

	int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
	if (fd < 0) { perror("socket"); return 1; }
	struct sockaddr_ll sa; memset(&sa, 0, sizeof sa);
	sa.sll_family = AF_PACKET; sa.sll_protocol = htons(ETH_P_ALL);
	sa.sll_ifindex = if_nametoindex(ifname);
	if (!sa.sll_ifindex) { perror("if_nametoindex"); return 1; }
	if (bind(fd, (struct sockaddr *)&sa, sizeof sa) < 0) { perror("bind"); return 1; }
	struct timeval rt = { 1, 0 };
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &rt, sizeof rt);

	double t0 = now_ms(), last = t0;
	unsigned in_n = 0, out_n = 0, in_b = 0, out_b = 0, bad_in = 0, bad_out = 0, shown = 0;
	unsigned types_in[8] = {0}, types_out[8] = {0};
	static uint8_t buf[4096];

	printf("слушаю %s, адрес %s, %d с%s\n", ifname, argv[2], secs, verbose ? " (все пакеты)" : "");
	fflush(stdout);
	while (now_ms() - t0 < secs * 1000.0) {
		struct sockaddr_ll from; socklen_t fl = sizeof from;
		int n = recvfrom(fd, buf, sizeof buf, 0, (struct sockaddr *)&from, &fl);
		double t = now_ms();
		if (n > 0) {
			uint8_t *p = buf; int len = n;
			if (len < 14) goto tick;
			uint16_t et = (p[12] << 8) | p[13]; p += 14; len -= 14;
			if (et == 0x8100 && len >= 4) { et = (p[2] << 8) | p[3]; p += 4; len -= 4; }
			if (et != 0x0800 || len < 20) goto tick;
			int ihl = (p[0] & 15) * 4;
			if ((p[0] >> 4) != 4 || ihl < 20 || len < ihl + 8 || p[9] != 17) goto tick;
			struct in_addr s, d; memcpy(&s, p + 12, 4); memcpy(&d, p + 16, 4);
			if (s.s_addr != want.s_addr && d.s_addr != want.s_addr) goto tick;
			int out = (from.sll_pkttype == PACKET_OUTGOING);
			uint8_t *u = p + ihl;
			unsigned sp = (u[0] << 8) | u[1], dp = (u[2] << 8) | u[3], ul = (u[4] << 8) | u[5], ck = (u[6] << 8) | u[7];
			int csum_state = 0; /* 0 нет суммы, 1 верна, 2 неверна */
			if (ck) {
				if ((int)ul > len - ihl) ul = len - ihl;
				uint32_t sum = csum_add(0, p + 12, 8); sum += 17; sum += ul;
				sum = csum_add(sum, u, ul);
				while (sum >> 16) sum = (sum & 0xffff) + (sum >> 16);
				csum_state = (sum == 0xffff) ? 1 : 2;
			}
			unsigned wg = 0; int ty = 0;
			if (ul >= 12) { wg = u[8] | (u[9] << 8) | (u[10] << 16) | ((unsigned)u[11] << 24); ty = (wg >= 1 && wg <= 4) ? (int)wg : 0; }
			if (out) { out_n++; out_b += n; if (csum_state == 2) bad_out++; types_out[ty]++; }
			else     { in_n++;  in_b += n;  if (csum_state == 2) bad_in++;  types_in[ty]++; }
			if (verbose || shown < 60) {
				shown++;
				printf("%7.3f %s ", (t - t0) / 1000.0, out ? "OUT" : "IN ");
				printf("%s:%u > ", inet_ntoa(s), sp); printf("%s:%u frame=%d udp=%u csum=%s wg=%u\n",
				       inet_ntoa(d), dp, n, ul, csum_state == 0 ? "none" : csum_state == 1 ? "ok" : "BAD", wg);
			}
		}
tick:
		if (t - last >= 1000.0) {
			printf("--- t=%3.0fs IN=%u (%uB) OUT=%u (%uB) badcsum in/out=%u/%u  wg-типы IN[1/2/3/4/другие]=%u/%u/%u/%u/%u OUT=%u/%u/%u/%u/%u\n",
			       (t - t0) / 1000.0, in_n, in_b, out_n, out_b, bad_in, bad_out,
			       types_in[1], types_in[2], types_in[3], types_in[4], types_in[0],
			       types_out[1], types_out[2], types_out[3], types_out[4], types_out[0]);
			fflush(stdout);
			last = t;
		}
	}
	return 0;
}
