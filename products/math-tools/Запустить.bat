@echo off
rem Десктоп-версия С активацией.
rem После сборки запускает готовый EXE; в разработке — через оболочку product-core.
setlocal
set "EXE=%~dp0builds\windows\Mathtools\Mathtools.exe"
if exist "%EXE%" (
  start "" "%EXE%"
) else (
  echo Сборка не найдена. Запускаю режим разработки (нужен Python + product-core)...
  pushd "%~dp0"
  python main.py
  popd
)
endlocal
