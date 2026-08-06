# -*- coding: utf-8 -*-
"""
Сборка Windows EXE из product.json.

Шаги:
1. Читает product.json и _secret.py из папки продукта.
2. Staging: копирует content/, _secret.py, product.json в _build_staging.
3. Генерирует .ico из SVG-иконки.
4. Запускает PyInstaller (--onedir --windowed).
5. Удаляет лишнее из бандла (slim).
6. Опционально создаёт Inno Setup инсталлятор.

Вызов:
    python -m build.windows <путь_к_папке_продукта> [--no-installer] [--clean]
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Путь к product-core
CORE_ROOT = Path(__file__).resolve().parent.parent
SHELL_DIR = CORE_ROOT / "product_core" / "shell"

# Модули PySide6, которые НЕ нужны (тот же список, что в interactive-posters)
PYSIDE6_EXCLUDES = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
    "PySide6.QtSerialBus", "PySide6.QtSerialPort",
    "PySide6.QtCharts", "PySide6.QtChartsQml", "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtGraphsWidgets",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtTest", "PySide6.QtUiTools",
    "PySide6.QtHttpServer", "PySide6.QtNetworkAuth",
    "PySide6.QtRemoteObjects", "PySide6.QtWebSockets",
    "PySide6.QtLocation", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
    "PySide6.QtScxml", "PySide6.QtSql", "PySide6.QtStateMachine",
    "PySide6.QtSvgWidgets", "PySide6.QtXml", "PySide6.QtDBus",
]


def log(msg: str):
    print(f"[build-win] {msg}")


def load_product(product_dir: Path) -> dict:
    cfg_path = product_dir / "product.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Нет product.json в {product_dir}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare_staging(product_dir: Path, cfg: dict) -> Path:
    """Копирует content, _secret.py, product.json, shell templates в staging."""
    staging = product_dir / "_build_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    # content/
    content_src = product_dir / cfg.get("content_dir", "content")
    if content_src.exists():
        shutil.copytree(content_src, staging / "content")
        log(f"content/ скопирован ({sum(1 for _ in (staging/'content').rglob('*'))} файлов)")

    # product.json
    shutil.copy2(product_dir / "product.json", staging / "product.json")

    # _secret.py
    secret = product_dir / "_secret.py"
    if secret.exists():
        shutil.copy2(secret, staging / "_secret.py")
    else:
        log("⚠ _secret.py не найден — лицензирование не будет работать")

    # Шаблоны оболочки (activation.html)
    templates_src = SHELL_DIR / "templates"
    templates_dst = staging / "content" / "templates"
    templates_dst.mkdir(parents=True, exist_ok=True)
    if templates_src.exists():
        for f in templates_src.iterdir():
            shutil.copy2(f, templates_dst / f.name)

    # Иконка
    icon_rel = cfg.get("icon", "assets/icon.svg")
    icon_src = product_dir / icon_rel
    if icon_src.exists():
        shutil.copy2(icon_src, staging / "icon.svg")

    return staging


def make_ico(staging: Path) -> Path:
    """SVG → PNG → ICO. Возвращает путь к .ico."""
    svg = staging / "icon.svg"
    ico_path = staging / "icon.ico"
    png_path = staging / "icon.png"

    if not svg.exists():
        log("⚠ Нет icon.svg, иконка по умолчанию")
        return ico_path

    try:
        from PySide6.QtCore import QSize, Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtWidgets import QApplication
        from PIL import Image

        if not QApplication.instance():
            QApplication(sys.argv)

        renderer = QSvgRenderer(str(svg))
        img = QImage(QSize(512, 512), QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        img.save(str(png_path), "PNG")

        pil = Image.open(png_path)
        pil.save(str(ico_path), format="ICO",
                 sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        log(f"Иконка: {ico_path}")
    except Exception as e:
        log(f"⚠ Не удалось создать .ico: {e}")
    return ico_path


def run_pyinstaller(product_dir: Path, staging: Path, cfg: dict, ico: Path) -> Path:
    """Запускает PyInstaller. Возвращает путь к бандлу."""
    slug = cfg["slug"]
    app_name = slug.replace("-", "").replace("_", "").capitalize()
    builds_dir = product_dir / "builds" / "windows"
    builds_dir.mkdir(parents=True, exist_ok=True)
    work_dir = product_dir / "_build_temp"
    work_dir.mkdir(exist_ok=True)

    sep = ";" if platform.system() == "Windows" else ":"

    # main.py продукта как точка входа. Если нет — генерируем минимальный.
    main_py = product_dir / "main.py"
    if not main_py.exists():
        main_py = staging / "_main_generated.py"
        main_py.write_text(
            "import sys, os\n"
            "sys.path.insert(0, os.path.dirname(__file__))\n"
            "from product_core.shell import run\n"
            "run(__file__)\n",
            encoding="utf-8")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        f"--name={app_name}",
        # Путь к исходникам product-core: editable-установку (PEP 660) PyInstaller
        # не прослеживает, поэтому указываем папку ядра напрямую — иначе PySide6/
        # QtWebEngine не попадут в сборку.
        f"--paths={CORE_ROOT}",
        f"--add-data={staging / 'content'}{sep}content",
        f"--add-data={staging / 'product.json'}{sep}.",
    ]

    if (staging / "_secret.py").exists():
        cmd.append(f"--add-data={staging / '_secret.py'}{sep}.")

    if ico.exists():
        cmd.append(f"--icon={ico}")
        cmd.append(f"--add-data={staging / 'icon.svg'}{sep}.")

    # Шаблоны оболочки (activation.html) — туда, где их ищет shell.app
    # (относительно своего __file__: product_core/shell/templates/).
    # Без этого в собранном EXE экран активации будет пустым.
    shell_templates = SHELL_DIR / "templates"
    if shell_templates.exists():
        cmd.append(f"--add-data={shell_templates}{sep}product_core/shell/templates")

    engine = (cfg.get("engine", "webview2") or "webview2").lower()

    cmd += [
        "--hidden-import=product_core",
        "--hidden-import=product_core.shell",
        "--hidden-import=product_core.shell.common",
        "--hidden-import=product_core.licensing",
        "--hidden-import=product_core._protocol",
        "--hidden-import=product_core.device_id",
        "--hidden-import=product_core.config",
        # Ed25519-проверка лицензий импортируется лениво — собираем cryptography явно
        "--hidden-import=cryptography",
        "--hidden-import=cryptography.hazmat.primitives.asymmetric.ed25519",
        "--collect-all=cryptography",
    ]

    if engine == "qt":
        cmd += [
            "--hidden-import=product_core.shell.app",
            *[f"--exclude-module={m}" for m in PYSIDE6_EXCLUDES],
        ]
    else:  # webview2 — системный движок Edge; Qt/Chromium НЕ бандлим
        cmd += [
            "--hidden-import=product_core.shell.app_webview2",
            "--hidden-import=webview",
            "--hidden-import=webview.platforms.edgechromium",
            "--hidden-import=clr",
            "--collect-data=webview",     # только JS-ассеты pywebview (нужны рантайму)
            "--collect-all=clr_loader",
            "--collect-all=pythonnet",
            # НЕ тянуть Qt/Chromium, другие GUI-бэкенды pywebview и научный стек:
            "--exclude-module=PySide6", "--exclude-module=PyQt5",
            "--exclude-module=PyQt6", "--exclude-module=PySide2",
            "--exclude-module=numpy", "--exclude-module=PIL",
            "--exclude-module=scipy", "--exclude-module=matplotlib",
            "--exclude-module=pandas", "--exclude-module=tkinter",
            "--exclude-module=Pythonwin",
            "--exclude-module=webview.platforms.qt",
            "--exclude-module=webview.platforms.gtk",
            "--exclude-module=webview.platforms.cef",
            "--exclude-module=webview.platforms.cocoa",
            "--exclude-module=webview.platforms.android",
        ]

    cmd += [
        "--distpath", str(builds_dir),
        "--workpath", str(work_dir),
        "--specpath", str(product_dir),
        str(main_py),
    ]

    log("PyInstaller…")
    result = subprocess.run(cmd, cwd=str(product_dir))
    if result.returncode != 0:
        raise RuntimeError("PyInstaller завершился с ошибкой")

    bundle = builds_dir / app_name
    if not bundle.exists():
        raise RuntimeError(f"PyInstaller не создал: {bundle}")
    log(f"✅ Бандл: {bundle}")
    return bundle


def slim_bundle(bundle: Path):
    """Удаляет неиспользуемые Qt-компоненты из бандла."""
    pyside = bundle / "_internal" / "PySide6"
    if not pyside.exists():
        return
    saved = 0
    # Удаляем debug ресурсы, devtools, неиспользуемые локали
    res = pyside / "resources"
    if res.exists():
        for p in res.iterdir():
            n = p.name.lower()
            if n.endswith(".debug.pak") or "devtools" in n:
                saved += p.stat().st_size
                p.unlink()
    # opengl32sw.dll
    sw = pyside / "opengl32sw.dll"
    if sw.exists():
        saved += sw.stat().st_size
        sw.unlink()
    if saved > 0:
        log(f"Slim: -{saved / 1024 / 1024:.1f} МБ")


def encrypt_content_dir(staging: Path, product_id: int):
    """Шифрует staging/content ключом контента продукта (из ecosystem.keys).

    Этот же ключ НЕ кладётся в сборку — он приходит внутри подписанной лицензии.
    В установщик попадает только шифртекст: копирование папки даёт мусор, а без
    купленной лицензии ключа для расшифровки нет вовсе.
    """
    keystore = CORE_ROOT / "ecosystem.keys"
    if not keystore.exists():
        log("⚠ ecosystem.keys не найден — контент НЕ шифруется (запустите keygen init)")
        return
    from product_core import _protocol as proto
    ks = json.loads(keystore.read_text(encoding="utf-8"))
    key = proto.derive_content_key(bytes.fromhex(ks["content_master"]), product_id)
    content = staging / "content"
    n, total = 0, 0
    for p in content.rglob("*"):
        if p.is_file():
            data = p.read_bytes()
            p.write_bytes(proto.encrypt_content(data, key))
            n += 1
            total += len(data)
    log(f"🔒 Контент зашифрован: {n} файлов ({total / 1024:.0f} КБ)")


def _find_iscc():
    for c in (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
              r"C:\Program Files\Inno Setup 6\ISCC.exe"):
        if os.path.exists(c):
            return c
    return shutil.which("ISCC")


_ISS_TEMPLATE = """; Автосгенерировано product-core
#define MyAppName "@NAME@"
#define MyAppVersion "@VERSION@"
#define MyAppPublisher "@PUBLISHER@"
#define MyAppExeName "@EXE@"

[Setup]
AppId={{@APPID@}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\\@APPDIR@
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\\{#MyAppExeName}
OutputDir=@OUTDIR@
OutputBaseFilename=@OUTBASE@
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
@SETUPICON@
DisableProgramGroupPage=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: checkedonce

[Files]
Source: "@BUNDLE@\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{group}\\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
@WEBVIEW2_CHECK@
"""


# Проверка наличия Edge WebView2 (только для движка webview2). Если рантайма нет —
# тихо ставим автономный установщик, лежащий рядом с Setup (на флешке), либо
# предупреждаем. На Windows 11 и почти всех Windows 10 рантайм уже есть.
_WV2_CODE = r"""
[Code]
function WV2Installed(): Boolean;
var v: String;
begin
  Result := False;
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}}', 'pv', v) then
    if (v <> '') and (v <> '0.0.0.0') then Result := True;
  if (not Result) and RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}}', 'pv', v) then
    if (v <> '') and (v <> '0.0.0.0') then Result := True;
end;

function InitializeSetup(): Boolean;
var rt: String; rc: Integer;
begin
  Result := True;
  if WV2Installed() then Exit;
  rt := ExpandConstant('{src}\MicrosoftEdgeWebView2RuntimeInstaller.exe');
  if FileExists(rt) then
    Exec(rt, '/silent /install', '', SW_SHOW, ewWaitUntilTerminated, rc)
  else
    if MsgBox('Программе нужен компонент Microsoft Edge WebView2 (есть в Windows 11 и почти на всех Windows 10).'#13#10 +
              'Если приложение не запустится — установите WebView2 Runtime. Продолжить установку?',
              mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
end;
"""


def make_installer(product_dir: Path, bundle: Path, cfg: dict, ico: Path):
    """Собирает Setup.exe через Inno Setup. Возвращает путь или None."""
    iscc = _find_iscc()
    if not iscc:
        log("⚠ Inno Setup (ISCC.exe) не найден — установщик пропущен (бандл готов)")
        return None
    slug = cfg["slug"]
    app_name = slug.replace("-", "").replace("_", "").capitalize()
    out_dir = product_dir / "builds" / "windows"
    out_base = f"{app_name}-Setup-{cfg.get('version', '1.0.0')}"
    setup_icon = (f"SetupIconFile={ico}" if ico and ico.exists() else "")

    iss_text = (_ISS_TEMPLATE
                .replace("@NAME@", cfg.get("name", slug))
                .replace("@VERSION@", cfg.get("version", "1.0.0"))
                .replace("@PUBLISHER@", cfg.get("publisher", "Oi-Orda"))
                .replace("@EXE@", f"{app_name}.exe")
                .replace("@APPID@", f"OiOrda-Product-{cfg.get('product_id', 0)}-{slug}")
                .replace("@APPDIR@", app_name)
                .replace("@OUTDIR@", str(out_dir))
                .replace("@OUTBASE@", out_base)
                .replace("@SETUPICON@", setup_icon)
                .replace("@BUNDLE@", str(bundle))
                .replace("@WEBVIEW2_CHECK@",
                         _WV2_CODE if (cfg.get("engine", "webview2") or "webview2").lower() != "qt"
                         else ""))

    iss_path = product_dir / f"{slug}.iss"
    iss_path.write_text(iss_text, encoding="utf-8-sig")  # Inno 6 читает UTF-8 с BOM

    log("Inno Setup…")
    result = subprocess.run([iscc, str(iss_path)], cwd=str(product_dir),
                            capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0:
        log(f"⚠ ISCC завершился с ошибкой:\n{(result.stdout or '')[-800:]}\n{(result.stderr or '')[-400:]}")
        return None
    setup_exe = out_dir / f"{out_base}.exe"
    if setup_exe.exists():
        log(f"✅ Установщик: {setup_exe} ({setup_exe.stat().st_size / 1024 / 1024:.1f} МБ)")
        return setup_exe
    log("⚠ ISCC отработал, но Setup.exe не найден")
    return None


def _has_msvc() -> bool:
    if shutil.which("cl"):
        return True
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) \
        / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        try:
            out = subprocess.run(
                [str(vswhere), "-latest", "-products", "*", "-requires",
                 "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                 "-property", "installationPath"],
                capture_output=True, text=True)
            return bool(out.stdout.strip())
        except Exception:
            return False
    return False


def run_nuitka(product_dir: Path, staging: Path, cfg: dict, ico: Path) -> Path:
    """Компилирует продукт в машинный код (Nuitka). Защищённый режим: нет .pyc/PYZ."""
    slug = cfg["slug"]
    app_name = slug.replace("-", "").replace("_", "").capitalize()
    builds_dir = product_dir / "builds" / "windows"
    builds_dir.mkdir(parents=True, exist_ok=True)
    work_dir = product_dir / "_build_temp"
    work_dir.mkdir(exist_ok=True)
    shell_templates = SHELL_DIR / "templates"

    main_py = product_dir / "main.py"
    if not main_py.exists():
        main_py = staging / "_main_generated.py"
        main_py.write_text(
            "from product_core.shell import run\nrun(__file__)\n", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        f"--output-dir={work_dir}",
        f"--output-filename={app_name}.exe",
        f"--include-data-dir={staging / 'content'}=content",
        f"--include-data-files={staging / 'product.json'}=product.json",
        "--include-package=product_core",
        "--include-package=cryptography",
        "--include-module=cryptography.hazmat.primitives.asymmetric.ed25519",
        f"--include-data-dir={shell_templates}=product_core/shell/templates",
    ]
    if (staging / "_secret.py").exists():
        cmd.append(f"--include-data-files={staging / '_secret.py'}=_secret.py")
    if ico.exists():
        cmd.append(f"--windows-icon-from-ico={ico}")
        cmd.append(f"--include-data-files={staging / 'icon.svg'}=icon.svg")
    if not _has_msvc():
        cmd.append("--mingw64")   # компилятора нет — Nuitka скачает MinGW64

    cmd.append(str(main_py))      # главный модуль (был пропущен!)

    log("Nuitka: компиляция в машинный код (долго; первый раз ещё и качает MinGW64)…")
    result = subprocess.run(cmd, cwd=str(product_dir))
    if result.returncode != 0:
        raise RuntimeError("Nuitka завершилась с ошибкой")

    dist = work_dir / (main_py.stem + ".dist")
    if not dist.exists():
        cands = list(work_dir.glob("*.dist"))
        dist = cands[0] if cands else dist
    if not dist.exists():
        raise RuntimeError(f"Nuitka не создала .dist: {dist}")

    bundle = builds_dir / app_name
    if bundle.exists():
        shutil.rmtree(bundle)
    shutil.move(str(dist), str(bundle))
    log(f"✅ Бандл (Nuitka, машинный код): {bundle}")
    return bundle


def build_windows(product_dir: str, no_installer: bool = False, clean: bool = False,
                  use_nuitka: bool = False):
    """Главная функция сборки Windows."""
    product_dir = Path(product_dir).resolve()
    cfg = load_product(product_dir)

    engine = (cfg.get("engine", "webview2") or "webview2").lower()
    if use_nuitka and engine != "qt":
        log("⚠ Nuitka поддерживается только с движком qt (pythonnet несовместим с Nuitka). "
            "Для webview2 собираю PyInstaller — движок системный, размер тот же.")
        use_nuitka = False

    log(f"Сборка: {cfg.get('name', cfg['slug'])} v{cfg.get('version', '1.0.0')} "
        f"[движок={engine}, {'Nuitka' if use_nuitka else 'PyInstaller'}]")

    if clean:
        for d in ("_build_staging", "_build_temp", "builds"):
            p = product_dir / d
            if p.exists():
                shutil.rmtree(p)
                log(f"Удалено: {p}")

    staging = prepare_staging(product_dir, cfg)
    ico = make_ico(staging)
    if cfg.get("security", {}).get("skip_activation", False):
        log("skip_activation — контент не шифруется")
    else:
        encrypt_content_dir(staging, int(cfg["product_id"]))   # шифруем ДО упаковки

    if use_nuitka:
        bundle = run_nuitka(product_dir, staging, cfg, ico)
    else:
        bundle = run_pyinstaller(product_dir, staging, cfg, ico)
        slim_bundle(bundle)

    if not no_installer:
        make_installer(product_dir, bundle, cfg, ico)

    log(f"📁 Результат ({'Nuitka' if use_nuitka else 'PyInstaller'}): {bundle}")
    return bundle


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Сборка Windows EXE из product.json")
    ap.add_argument("product_dir", help="Путь к папке продукта с product.json")
    ap.add_argument("--no-installer", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--nuitka", action="store_true")
    args = ap.parse_args()
    build_windows(args.product_dir, args.no_installer, args.clean, use_nuitka=args.nuitka)
