# -*- coding: utf-8 -*-
"""
Единый билд-оркестратор: одна команда → Windows EXE + Android APK.

Использование:
    python -m build <путь_к_папке_продукта>                 # Win + Android
    python -m build <путь> --windows                        # Только Windows
    python -m build <путь> --android                        # Только Android
    python -m build <путь> --clean                          # Очистить перед сборкой
    python -m build <путь> --android --debug                # Android debug
    python -m build <путь> --no-installer                   # Win без Inno Setup
"""

import argparse
import sys
import time


def main():
    ap = argparse.ArgumentParser(
        description="Единая сборка Windows + Android из product.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("product_dir", help="Путь к папке продукта с product.json")
    ap.add_argument("--windows", "-w", action="store_true", help="Собрать только Windows")
    ap.add_argument("--android", "-a", action="store_true", help="Собрать только Android")
    ap.add_argument("--clean", action="store_true", help="Очистить перед сборкой")
    ap.add_argument("--debug", "-d", action="store_true", help="Android debug build")
    ap.add_argument("--no-installer", action="store_true", help="Без Inno Setup")
    ap.add_argument("--legacy20", action="store_true",
                    help="Запасная сборка: активация коротким ключом (20 симв.), "
                         "ключ контента встроен в APK — защита слабее")
    ap.add_argument("--nuitka", action="store_true",
                    help="Защищённый режим: компиляция в машинный код (медленнее)")
    args = ap.parse_args()

    # Если ни --windows, ни --android не указаны — собираем оба
    do_win = args.windows or (not args.windows and not args.android)
    do_android = args.android or (not args.windows and not args.android)

    results = {}
    t0 = time.time()

    if do_win:
        print("\n" + "=" * 60)
        print("  🖥️  WINDOWS BUILD")
        print("=" * 60)
        try:
            from .windows import build_windows
            bundle = build_windows(args.product_dir, args.no_installer, args.clean,
                                   use_nuitka=args.nuitka)
            results["windows"] = ("✅", str(bundle))
        except Exception as e:
            results["windows"] = ("❌", str(e))
            print(f"❌ Windows: {e}")

    if do_android:
        print("\n" + "=" * 60)
        print("  📱  ANDROID BUILD")
        print("=" * 60)
        try:
            from .android import build_android
            apk = build_android(args.product_dir, args.debug, legacy20=args.legacy20)
            results["android"] = ("✅", str(apk) if apk else "APK не найден")
        except Exception as e:
            results["android"] = ("❌", str(e))
            print(f"❌ Android: {e}")

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print(f"  ИТОГО ({elapsed:.0f} сек)")
    print("=" * 60)
    for target, (status, path) in results.items():
        print(f"  {status} {target:10} → {path}")
    print("=" * 60 + "\n")

    # Exit code: 0 если хотя бы одна сборка успешна
    if any(s == "✅" for s, _ in results.values()):
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
