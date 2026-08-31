# -*- coding: utf-8 -*-
"""
Сборка Android APK из product.json.

Одно-вариантный продукт → один APK (<slug>-release.apk).
Много-вариантный (product.json variants > 1) → по APK на вариант
(<slug>-<variant_slug>-release.apk): контент фильтруется под предмет и шифруется
ключом варианта derive_content_key(master, product_id, variant_id) — как флейворы
плакатов, но из одного продукта. applicationId делается уникальным на вариант,
чтобы приложения предметов сосуществовали на устройстве.

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


def _content_key(product_id: int, variant_id: int = 0):
    """Ключ контента продукта/варианта из ecosystem.keys (None, если ключей нет)."""
    keystore = CORE_ROOT / "ecosystem.keys"
    if not keystore.exists():
        return None
    from product_core import _protocol as proto
    ks = json.loads(keystore.read_text(encoding="utf-8"))
    return proto.derive_content_key(bytes.fromhex(ks["content_master"]), product_id, variant_id)


def _encrypt_assets_content(content_dir: Path, product_id: int, variant_id: int = 0):
    """Шифрует assets/content/* ключом контента продукта (variant 0 = как раньше)."""
    keystore = CORE_ROOT / "ecosystem.keys"
    if not keystore.exists():
        log("⚠ ecosystem.keys не найден — контент НЕ шифруется")
        return
    from product_core import _protocol as proto
    ks = json.loads(keystore.read_text(encoding="utf-8"))
    key = proto.derive_content_key(bytes.fromhex(ks["content_master"]), product_id, variant_id)
    n = 0
    for p in content_dir.rglob("*"):
        if p.is_file():
            p.write_bytes(proto.encrypt_content(p.read_bytes(), key))
            n += 1
    log(f"🔒 Контент зашифрован: {n} файлов (вариант {variant_id})")


def _filter_content_for_variant(content_dir: Path, variant_slug: str):
    """Оставляет в content только контент варианта (предмета). all/None — не трогает.

    Конвенция: посты предмета лежат в content/posters/<slug>/, а data.json имеет
    subjects[].key. Для варианта <slug> удаляем posters/<другие> и оставляем в
    data.json только этот предмет."""
    if not variant_slug or variant_slug == "all":
        return
    posters = content_dir / "posters"
    if posters.is_dir():
        for d in list(posters.iterdir()):
            if d.is_dir() and d.name != variant_slug:
                shutil.rmtree(d)
    dj = content_dir / "data.json"
    if dj.exists():
        try:
            data = json.loads(dj.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("subjects"), list):
                data["subjects"] = [s for s in data["subjects"] if s.get("key") == variant_slug]
                dj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:  # noqa
            log(f"⚠ data.json не отфильтрован: {e}")


def build_android(product_dir: str, debug: bool = False, legacy20: bool = False):
    """Собирает APK продукта. Много-вариантный продукт → список APK, иначе один APK.

    legacy20=True — «запасная» сборка с активацией коротким ключом (20 символов):
    ключ контента кладётся В APK (обфусцирован XOR-маской), поэтому активация
    возможна без QR и без длинной лицензии. Защита слабее — контент можно достать
    из APK, — поэтому такие сборки только как крайний вариант.
    """
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
    variants = cfg.get("variants") or [{"id": 0, "slug": "all", "name": name}]
    multi = len(variants) > 1
    skip_act = cfg.get("security", {}).get("skip_activation", False)

    log(f"Сборка: {name} v{version} (Android)" + (f" — {len(variants)} вариантов" if multi else ""))

    # 1. android_shell → ASCII-temp (Gradle не собирает из путей с кириллицей)
    build_base = os.environ.get("OILAB_BUILD_DIR") or tempfile.gettempdir()
    work = Path(build_base) / f"oilab_android_{slug}"
    if not _is_ascii(str(work)):
        log(f"⚠ путь сборки не-ASCII: {work} — задайте OILAB_BUILD_DIR (напр. D:\\oilab_build)")
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(ANDROID_SHELL, work)
    log(f"Каталог сборки: {work}")

    sdk = (os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
           or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"))
    if os.path.isdir(sdk):
        (work / "local.properties").write_text("sdk.dir=" + sdk.replace("\\", "/") + "\n", encoding="utf-8")
        log(f"Android SDK: {sdk}")
    else:
        log("⚠ Android SDK не найден — задайте ANDROID_SDK_ROOT")

    gradlew = "gradlew.bat" if platform.system() == "Windows" else "gradlew"
    gradlew_path = work / gradlew
    if not gradlew_path.exists():
        log("⚠ gradlew не найден. Нужен Gradle wrapper.")
        return None

    gradle_app = work / "app" / "build.gradle.kts"
    gradle_orig = gradle_app.read_text(encoding="utf-8")   # исходный текст — подставляем на каждый вариант
    strings_xml = work / "app" / "src" / "main" / "res" / "values" / "strings.xml"
    assets_dir = work / "app" / "src" / "main" / "assets"
    content_src = product_dir / cfg.get("content_dir", "content")
    pub = _load_public_key(product_dir)
    builds_dir = product_dir / "builds" / "android"
    builds_dir.mkdir(parents=True, exist_ok=True)
    bt_dir = "debug" if debug else "release"
    task = "assembleDebug" if debug else "assembleRelease"

    apks = []
    for v in variants:
        vslug = v.get("slug", "all")
        vid = int(v.get("id", 0))
        vname = v.get("name", name)
        disp = vname if multi else name
        # applicationId уникален на вариант (кроме "all"/одно-вариантного) — чтобы приложения сосуществовали
        appid = namespace if (not multi or vslug == "all") else f"{namespace}.{vslug.replace('-', '')}"

        # build.gradle.kts (из исходного текста каждый раз)
        gtxt = gradle_orig.replace('applicationId = "kz.digitouch.shell"', f'applicationId = "{appid}"')
        gtxt = gtxt.replace('versionName = "1.0.0"', f'versionName = "{version}"')
        gradle_app.write_text(gtxt, encoding="utf-8")

        # strings.xml (app_name)
        strings_xml.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
            f'    <string name="app_name">{disp}</string>\n</resources>\n',
            encoding="utf-8")

        # content → assets/content (сброс + фильтр варианта + шифрование ключом варианта)
        cdst = assets_dir / "content"
        if cdst.exists():
            shutil.rmtree(cdst)
        if content_src.exists():
            shutil.copytree(content_src, cdst)
            if multi:
                _filter_content_for_variant(cdst, vslug)
            if not skip_act:
                _encrypt_assets_content(cdst, cfg.get("product_id", 0), vid)
            else:
                log("skip_activation — контент не шифруется")

        # templates (activation.html) — plaintext
        templates_dst = assets_dir / "templates"
        templates_dst.mkdir(exist_ok=True)
        if SHELL_TEMPLATES.exists():
            for f in SHELL_TEMPLATES.iterdir():
                shutil.copy2(f, templates_dst / f.name)

        # product_config.json (v4: публичный ключ + вариант; ключа контента в APK нет)
        product_config = {
            "product_id": cfg.get("product_id", 0),
            "variant_id": vid,
            "entry_html": cfg.get("entry_html", "index.html"),
            "window_title": disp,
            "anti_copy": cfg.get("security", {}).get("anti_copy", True),
            "flag_secure": cfg.get("security", {}).get("flag_secure", True),
            "skip_activation": skip_act,
        }
        if legacy20:
            # Ключ контента в APK для короткого ключа. XOR-маска — чтобы ключ
            # не лежал в assets открытым текстом (см. MainActivity: ck_mask^ck_data).
            ck = _content_key(cfg.get("product_id", 0), vid)
            if ck:
                mask = os.urandom(32)
                product_config["ck_mask"] = list(mask)
                product_config["ck_data"] = [m ^ c for m, c in zip(mask, ck)]
                log(f"🔓 legacy20 ({vslug}): ключ контента встроен в APK")
            else:
                log("⚠ legacy20: нет ecosystem.keys — короткий ключ работать не будет")
        if pub:
            product_config["public_key"] = pub
        else:
            log("⚠ публичный ключ не найден в _secret.py — активация не будет работать")
        (assets_dir / "product_config.json").write_text(
            json.dumps(product_config, ensure_ascii=False), encoding="utf-8")

        # Gradle
        log(f"Gradle ({vslug}): {task}")
        result = subprocess.run([str(gradlew_path), task, "--stacktrace"],
                                cwd=str(work), env=os.environ.copy())
        if result.returncode != 0:
            raise RuntimeError(f"Gradle сборка ({vslug}) завершилась с ошибкой")

        # APK → builds/android/
        apk_dir = work / "app" / "build" / "outputs" / "apk" / bt_dir
        apk_src = None
        if apk_dir.exists():
            for f in apk_dir.iterdir():
                if f.suffix == ".apk":
                    apk_src = f
                    break
        suffix = "-legacy20" if legacy20 else ""
        apk_name = (f"{slug}{suffix}-{bt_dir}.apk" if not multi
                    else f"{slug}-{vslug}{suffix}-{bt_dir}.apk")
        if apk_src and apk_src.exists():
            apk_dst = builds_dir / apk_name
            shutil.copy2(apk_src, apk_dst)
            size_mb = apk_dst.stat().st_size / (1024 * 1024)
            log(f"✅ APK: {apk_dst} ({size_mb:.1f} MB)")
            apks.append(apk_dst)
        else:
            log(f"⚠ APK не найден ({vslug})")

    return apks if multi else (apks[0] if apks else None)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Сборка Android APK из product.json")
    ap.add_argument("product_dir", help="Путь к папке продукта")
    ap.add_argument("--debug", "-d", action="store_true")
    args = ap.parse_args()
    build_android(args.product_dir, args.debug)
