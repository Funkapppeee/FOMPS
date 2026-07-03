@echo off
title FOMPS - deploy sync worker
cd /d "%~dp0worker"
echo ============================================================
echo  Deploying the FOMPS (openmpsync) sync worker to Cloudflare
echo ============================================================
echo.
echo  When it asks: "Would you like to register a workers.dev
echo  subdomain now?"  ->  type  Y  and press Enter,
echo  then type a short name (e.g.  fomps ) and press Enter.
echo.
echo  Your server URL will be:  openmpsync.^<name^>.workers.dev
echo ------------------------------------------------------------
echo.
call "%~dp0worker\node_modules\.bin\wrangler.cmd" deploy
echo.
echo ============================================================
echo  Copy the https://...workers.dev URL above and tell Claude.
echo ============================================================
pause
