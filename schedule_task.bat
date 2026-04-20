@echo off
REM Gunluk fiyat kontrolu icin Windows Gorev Zamanlayici gorevini olusturur.
REM Bu dosyayi SAG TIKLAYIP "Yonetici olarak calistir" ile ac.

set TASK_NAME=PriceMonitorBot
set PYTHON=python
set SCRIPT=%~dp0main.py
set HOUR=09
set MINUTE=00

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%SCRIPT%\"" ^
  /sc daily ^
  /st %HOUR%:%MINUTE% ^
  /rl highest ^
  /f

echo.
echo Gorev olusturuldu: Her gun saat %HOUR%:%MINUTE%'de calisacak.
echo Gormek icin: Gorev Zamanlayici ^(taskschd.msc^)
pause
