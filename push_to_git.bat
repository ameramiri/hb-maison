@echo off
REM ===== Push everything to Git (new folders/files included) =====

REM رفتن به مسیری که خود فایل bat داخلش است (ریشه پروژه)
cd /d %~dp0

echo.
echo ==== GIT STATUS (before) ====
git status -sb
echo ==============================

REM گرفتن پیام کامیت از کاربر
set msg=
set /p msg=Enter commit message: 

REM اگر خالی بود، پیام خودکار با تاریخ/ساعت بساز
if "%msg%"=="" (
    for /f "tokens=1-4 delims=/ " %%a in ("%date% %time%") do (
        set msg=auto-commit %%a %%b %%c %%d
    )
)

echo.
echo ---- Adding ALL changes (new/modified/deleted) ----
git add -A

REM چک کنیم چیزی برای کامیت هست یا نه
git diff --cached --quiet
if %errorlevel% NEQ 0 (
    echo.
    echo ---- Committing with message: "%msg%" ----
    git commit -m "%msg%"

    echo.
    echo ---- Pushing to origin/main ----
    git push origin main

    echo.
    echo ✅ Done: changes pushed.
) else (
    echo.
    echo ℹ️ No changes to commit. Nothing to push.
)

echo.
pause