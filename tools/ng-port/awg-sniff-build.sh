#!/bin/bash
# Собирает awg-sniff кросс-компилятором padavan-4.4 и копирует на роутер (/tmp/awg-sniff).
#   ./awg-sniff-build.sh [путь_к_padavan-4.4] [адрес_роутера]
REPO="${1:-$HOME/prometeus/update/padavan-4.4}"
ROUTER="${2:-192.168.2.1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CC="$(ls "$REPO"/toolchain-mipsel/toolchain-4.4.x/bin/*-gcc 2>/dev/null | head -1)"
[ -n "$CC" ] || { echo "Нет кросс-компилятора в $REPO/toolchain-mipsel/toolchain-4.4.x/bin"; exit 1; }
echo "компилятор: $CC"
"$CC" -O2 -static -Wall -o "$HERE/awg-sniff.mipsel" "$HERE/awg-sniff.c" || exit 1
file "$HERE/awg-sniff.mipsel" 2>/dev/null
echo "копирую на $ROUTER (понадобится пароль admin)..."
ssh admin@"$ROUTER" 'cat > /tmp/awg-sniff && chmod +x /tmp/awg-sniff' < "$HERE/awg-sniff.mipsel" && echo "готово: /tmp/awg-sniff на роутере"
