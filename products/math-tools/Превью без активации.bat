@echo off
rem Открывает контент в браузере БЕЗ активации — режим разработки/превью.
setlocal
set "HTML=%~dp0content\index.html"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
set "URL=file:///%HTML:\=/%"
if exist "%EDGE%" (
  start "" "%EDGE%" --app="%URL%" --window-size=1440,920
) else (
  start "" "%HTML%"
)
endlocal
