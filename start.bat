@echo off
title Starting server

setlocal
set SCRIPT_DIR=%~dp0
start pythonw "%SCRIPT_DIR%server.py"
