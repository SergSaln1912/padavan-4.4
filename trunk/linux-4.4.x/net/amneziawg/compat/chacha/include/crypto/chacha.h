/* SPDX-License-Identifier: GPL-2.0 */
/*
 * ng-port: переходник <crypto/chacha.h> для ядра 4.4.
 * Реализует интерфейс ядра >= 4.20 (chacha_init, chacha20_crypt) поверх собственного ChaCha20 модуля (zinc).
 * Раскладка состояния как в ядре: слова 0..3 константы, 4..11 ключ, 12 - счётчик блоков, 13..15 - nonce.
 */
#ifndef _AWG_COMPAT_CRYPTO_CHACHA_H
#define _AWG_COMPAT_CRYPTO_CHACHA_H

#include <linux/types.h>
#include <linux/string.h>
#include <asm/unaligned.h>
#include <zinc/chacha20.h>

#define CHACHA_KEY_SIZE		32
#define CHACHA_BLOCK_SIZE	64

static inline void chacha_init(u32 *state, const u32 *key, const u8 *iv)
{
	state[0]  = 0x61707865U;
	state[1]  = 0x3320646eU;
	state[2]  = 0x79622d32U;
	state[3]  = 0x6b206574U;
	state[4]  = key[0];
	state[5]  = key[1];
	state[6]  = key[2];
	state[7]  = key[3];
	state[8]  = key[4];
	state[9]  = key[5];
	state[10] = key[6];
	state[11] = key[7];
	state[12] = get_unaligned_le32(iv + 0);
	state[13] = get_unaligned_le32(iv + 4);
	state[14] = get_unaligned_le32(iv + 8);
	state[15] = get_unaligned_le32(iv + 12);
}

static inline void chacha20_crypt(u32 *state, u8 *dst, const u8 *src, unsigned int bytes)
{
	struct chacha20_ctx ctx;
	simd_context_t simd_context;

	memcpy(ctx.state, state, sizeof(ctx.state));
	simd_get(&simd_context);
	chacha20(&ctx, dst, src, bytes, &simd_context);
	simd_put(&simd_context);
	memcpy(state, ctx.state, sizeof(ctx.state));	/* счётчик блоков двигается, как в ядре */
}

#endif /* _AWG_COMPAT_CRYPTO_CHACHA_H */
