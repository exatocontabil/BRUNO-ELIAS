@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "RAIZ=%%~fI"
echo Criando o atalho do Exato na Area de Trabalho...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Exato Central Fiscal.lnk'); $s.TargetPath='%RAIZ%\INICIAR.bat'; $s.WorkingDirectory='%RAIZ%'; $s.IconLocation='%RAIZ%\programa\assets\exato_central_fiscal.ico'; $s.WindowStyle=7; $s.Description='Exato Central Fiscal'; $s.Save()"
if errorlevel 1 (echo [ERRO] Nao foi possivel criar o atalho.) else (echo Pronto! O atalho "Exato Central Fiscal" esta na Area de Trabalho, com o logo da Exato. Voce pode fixa-lo na barra de tarefas.)
echo.
pause
