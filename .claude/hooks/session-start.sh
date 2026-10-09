#!/bin/bash
# SessionStart-хук для облачных сессий Claude Code (claude.ai/code).
# Готовит контейнер так, чтобы сразу работали: keygen/лицензии, валидаторы
# продуктов (node tools/validate.js) и генератор QR (tools/qr.py).
# Локально (на компьютере разработчика) ничего не делает.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# 1. Python-зависимости: cryptography (лицензии Ed25519) + segno (QR-коды).
#    Оболочку (pywebview/PySide6) не ставим — в облаке нет экрана.
if ! python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore \
     "cryptography>=42" "segno>=1.6"; then
  echo "pip install не удался — keygen/QR могут не работать" >&2
fi

# 2. product_core импортируется без установки — через PYTHONPATH.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PYTHONPATH=\"$ROOT/product-core\${PYTHONPATH:+:\$PYTHONPATH}\"" >> "$CLAUDE_ENV_FILE"
fi

# 3. Ключи разработчика (опционально). Если в настройках облачного окружения
#    задан секрет OI_ORDA_ECOSYSTEM_KEYS (содержимое файла ecosystem.keys как
#    есть или в base64), восстанавливаем файл, чтобы работал keygen genlicense.
#    Файл в .gitignore и в коммит не попадёт.
KEYS_FILE="$ROOT/product-core/ecosystem.keys"
if [ -n "${OI_ORDA_ECOSYSTEM_KEYS:-}" ] && [ ! -f "$KEYS_FILE" ]; then
  umask 077
  case "$OI_ORDA_ECOSYSTEM_KEYS" in
    \{*) printf '%s' "$OI_ORDA_ECOSYSTEM_KEYS" > "$KEYS_FILE" ;;
    *)   printf '%s' "$OI_ORDA_ECOSYSTEM_KEYS" | base64 -d > "$KEYS_FILE" 2>/dev/null || true ;;
  esac
  if python3 -c "import json,sys; k=json.load(open(sys.argv[1])); assert 'ed25519_priv' in k and 'content_master' in k" "$KEYS_FILE" 2>/dev/null; then
    echo "ecosystem.keys восстановлен из OI_ORDA_ECOSYSTEM_KEYS"
  else
    rm -f "$KEYS_FILE"
    echo "OI_ORDA_ECOSYSTEM_KEYS задан, но это не корректный ecosystem.keys — пропускаю" >&2
  fi
fi

exit 0
