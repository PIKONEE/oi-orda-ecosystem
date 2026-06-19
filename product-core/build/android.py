# -*- coding: utf-8 -*-
"""
Сборка Android APK из product.json.

Шаги:
1. Копирует android_shell/ шаблон во временную папку.
2. Подставляет namespace, applicationId, app_name из product.json.
3. Копирует content/ в assets/content/.
4. Генерирует assets/product_config.json (с секретом для Licensing.kt).
5. Копирует activation.html шаблон.
6. Запускает gradlew assembleRelease.
7. Копирует APK в builds/android/.

Вызов:
    python -m build.android <путь_к_папке_продукта> [--debug]
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parent.parent
ANDROID_SHELL = CORE_ROOT / "android_shell"
SHELL_TEMPLATES = CORE_ROOT / "product_core" / "shell" / "templates"


def log(msg: str):
    print(f"[build-android] {msg}")


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _ensure_java_home():
    """Ищет JDK если JAVA_HOME не установлен."""
    if os.environ.get("JAVA_HOME"):
        return
    candidates = [
        r"D:\jdk17\jdk-17.0.18+8",
        r"D:\apps\jbr",
        os.path.join(os.environ.get("ProgramFiles", ""), "Android", "Android Studio", "jbr"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Android", "Android Studio", "jbr"),
    ]
    for path in candidates:
        if os.path.isfile(os.path.join(path, "bin", "java.exe" if platform.system() == "Windows" else "java")):
            os.environ["JAVA_HOME"] = path
            log(f"JAVA_HOME = {path}")
            return
    log("⚠ JAVA_HOME не найден. Установите JDK 17.")


def _load_public_key(product_dir: Path):
    """Читает публичный ключ Ed25519 из _secret.py (v4). Возвращает list[int] или None."""
    secret_path = product_dir / "_secret.py"
    if not secret_path.exists():
        return None
    ns: dict = {}
    with open(secret_path, "r", encoding="utf-8") as f:
        exec(compile(f.read(), str(secret_path), "exec"), ns)
    if "_PUB" in ns:
        return list(ns["_PUB"])
    if "get_public_key" in ns:
        return list(ns["get_public_key"]())
    return None


def _encrypt_assets_content(content_dir: Path, product_id: int):
    """Шифрует assets/content/* ключом контента продукта (как на Windows)."""
    keystore = CORE_ROOT / "ecosystem.keys"
    if not keystore.exists():
        log("⚠ ecosystem.keys не найден — контент НЕ шифруется")
        return
    from product_core import _protocol as proto
    ks = json.loads(keystore.read_text(encoding="utf-8"))
    key = proto.derive_content_key(bytes.fromhex(ks["content_master"]), product_id)
    n = 0
    for p in content_dir.rglob("*"):
        if p.is_file():
            p.write_bytes(proto.encrypt_content(p.read_bytes(), key))
            n += 1
    log(f"🔒 Контент зашифрован: {n} файлов")


def build_android(product_dir: str, debug: bool = False):
    """Главная функция сборки Android APK."""
    _ensure_java_home()

    product_dir = Path(product_dir).resolve()
    cfg_path = product_dir / "product.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Нет product.json в {product_dir}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    slug = cfg["slug"]
    name = cfg.get("name", slug)
    namespace = cfg.get("android_namespace", f"kz.digitouch.{slug.replace('-', '')}")
    version = cfg.get("version", "1.0.0")

    log(f"Сборка: {name} v{version} (Android)")

    # 1. Копируем android_shell в каталог сборки.
    #    ВАЖНО: путь сборки должен быть БЕЗ не-ASCII символов — Android Gradle Plugin
    #    отказывается собирать из путей с кириллицей (наш product_dir может быть таким,
    #    напр. D:\Windsurf\в\...). Поэтому собираем в ASCII-temp, исходники не трогаем.
    build_base = os.environ.get("OILAB_BUILD_DIR") or tempfile.gettempdir()
    work = Path(build_base) / f"oilab_android_{slug}"
    if not _is_ascii(str(work)):
        log(f"⚠ путь сборки не-ASCII: {work}")
        log("  задайте ASCII-путь через переменную окружения OILAB_BUILD_DIR (напр. D:\\oilab_build)")
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(ANDROID_SHELL, work)
    log(f"Каталог сборки: {work}")

    # local.properties с путём к Android SDK (иначе Gradle не найдёт SDK)
    sdk = (os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
           or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"))
    if os.path.isdir(sdk):
        (work / "local.properties").write_text("sdk.dir=" + sdk.replace("\\", "/") + "\n", encoding="utf-8")
        log(f"Android SDK: {sdk}")
    else:
        log("⚠ Android SDK не найден — задайте ANDROID_SDK_ROOT")

    # 2. Подставляем applicationId/версию в build.gradle.kts.
    #    namespace (пакет R/BuildConfig) НЕ трогаем — он должен совпадать с пакетом
    #    исходников kz.digitouch.shell, иначе `R` и `.MainActivity` не разрешатся.
    #    applicationId (id установки) делаем уникальным на продукт — он может отличаться.
    gradle_app = work / "app" / "build.gradle.kts"
    text = gradle_app.read_text(encoding="utf-8")
    text = text.replace('applicationId = "kz.digitouch.shell"', f'applicationId = "{namespace}"')
    text = text.replace('versionName = "1.0.0"', f'versionName = "{version}"')
    gradle_app.write_text(text, encoding="utf-8")

    # 3. Подставляем app_name в strings.xml
    strings = work / "app" / "src" / "main" / "res" / "values" / "strings.xml"
    strings.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        f'    <string name="app_name">{name}</string>\n</resources>\n',
        encoding="utf-8")

    # 4. Копируем content/ в assets/content/
    assets_dir = work / "app" / "src" / "main" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    content_src = product_dir / cfg.get("content_dir", "content")
    if content_src.exists():
        shutil.copytree(content_src, assets_dir / "content")
        log("content/ → assets/content/")
        if not cfg.get("security", {}).get("skip_activation", False):
            _encrypt_assets_content(assets_dir / "content", cfg.get("product_id", 0))
        else:
            log("skip_activation — контент не шифруется")

    # 5. Копируем activation.html шаблон
    templates_dst = assets_dir / "templates"
    templates_dst.mkdir(exist_ok=True)
    if SHELL_TEMPLATES.exists():
        for f in SHELL_TEMPLATES.iterdir():
            shutil.copy2(f, templates_dst / f.name)

    # 6. Генерируем product_config.json (v4: публичный ключ Ed25519 для Licensing.init)
    product_config = {
        "product_id": cfg.get("product_id", 0),
        "entry_html": cfg.get("entry_html", "index.html"),
        "window_title": cfg.get("name", slug),
        "anti_copy": cfg.get("security", {}).get("anti_copy", True),
        "flag_secure": cfg.get("security", {}).get("flag_secure", True),
        "skip_activation": cfg.get("security", {}).get("skip_activation", False),
    }
    pub = _load_public_key(product_dir)
    if pub:
        product_config["public_key"] = pub
    else:
        log("⚠ публичный ключ не найден в _secret.py — активация не будет работать")

    # Ключ контента (обфусцирован XOR-маской) — для короткого ключа активации
    # и расшифровки контента. Извлекаемо реверс-инженером = защита уровня v3 (как договорились).
    keystore = CORE_ROOT / "ecosystem.keys"
    if keystore.exists() and not cfg.get("security", {}).get("skip_activation", False):
        from product_core import _protocol as _proto
        _ks = json.loads(keystore.read_text(encoding="utf-8"))
        ckey = _proto.derive_content_key(bytes.fromhex(_ks["content_master"]), cfg.get("product_id", 0))
        mask = os.urandom(32)
        product_config["ck_mask"] = list(mask)
        product_config["ck_data"] = [ckey[i] ^ mask[i] for i in range(32)]
        log("ключ контента встроен (для короткого ключа)")
    with open(assets_dir / "product_config.json", "w", encoding="utf-8") as f:
        json.dump(product_config, f, ensure_ascii=False)
    log("product_config.json сгенерирован")

    # 7. Запускаем Gradle
    gradlew = "gradlew.bat" if platform.system() == "Windows" else "gradlew"
    gradlew_path = work / gradlew
    if not gradlew_path.exists():
        log("⚠ gradlew не найден. Нужен Gradle wrapper.")
        log("  Скопируйте gradle/ wrapper из любого Android-проекта.")
        return None

    build_type = "Debug" if debug else "Release"
    task = f"assemble{build_type}"
    log(f"Gradle: {task}")

    result = subprocess.run(
        [str(gradlew_path), task, "--stacktrace"],
        cwd=str(work), env=os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError("Gradle сборка завершилась с ошибкой")

    # 8. Копируем APK
    bt = "debug" if debug else "release"
    apk_dir = work / "app" / "build" / "outputs" / "apk" / bt
    apk_src = None
    if apk_dir.exists():
        for f in apk_dir.iterdir():
            if f.suffix == ".apk":
                apk_src = f
                break

    builds_dir = product_dir / "builds" / "android"
    builds_dir.mkdir(parents=True, exist_ok=True)

    if apk_src and apk_src.exists():
        apk_dst = builds_dir / f"{slug}-{bt}.apk"
        shutil.copy2(apk_src, apk_dst)
        size_mb = apk_dst.stat().st_size / (1024 * 1024)
        log(f"✅ APK: {apk_dst} ({size_mb:.1f} MB)")
        return apk_dst
    else:
        log("⚠ APK не найден в выходной папке Gradle")
        return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Сборка Android APK из product.json")
    ap.add_argument("product_dir", help="Путь к папке продукта")
    ap.add_argument("--debug", "-d", action="store_true")
    args = ap.parse_args()
    build_android(args.product_dir, args.debug)
