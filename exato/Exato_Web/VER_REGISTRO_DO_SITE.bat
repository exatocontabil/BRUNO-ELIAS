@echo off
rem Abre o registro do que o site escreveu (como ficava na janela preta).
if exist "%USERPROFILE%\ExatoWebDados\logs\servidor_saida.log" ( notepad "%USERPROFILE%\ExatoWebDados\logs\servidor_saida.log" ) else ( echo Ainda nao ha registro. O site ja foi ligado pela tarefa? & pause )
