@echo off
REM اسکریپت ساده برای push کردن روی گیت

REM رفتن به مسیر اسکریپت (در صورتی که از جای دیگری اجرا شود)
cd /d %~dp0

REM نمایش وضعیت فعلی
echo ==== GIT STATUS ====
git status
echo ====================

REM دریافت پیام کامیت از کاربر
set /p msg=Enter commit message: 

REM اگر خالی بود، پیام پیش‌فرض بگذار
if "%msg%"=="" set msg=update

echo.
echo ==== ADD, COMMIT, PUSH ====
git add -A
git commit -m "%msg%"
git push origin main
echo ===========================

pause
