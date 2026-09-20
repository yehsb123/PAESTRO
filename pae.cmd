@echo off
REM PAESTRO 런처(Windows) — `pae s "질의"` 처럼 쓰기 위한 래퍼. python pae.py 로 위임.
python "%~dp0pae.py" %*
