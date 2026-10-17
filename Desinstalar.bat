@echo off
title Personal Gamification Tracker - Desinstalar
rem Sai da pasta do programa para que ela possa ser apagada; tudo numa linha (o .bat sera apagado).
cd /d "%TEMP%" & powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall & exit /b
