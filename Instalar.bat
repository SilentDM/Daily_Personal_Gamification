@echo off
title Personal Gamification Tracker - Instalador
rem Instala tudo o que o programa precisa e cria o atalho na Area de Trabalho.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
