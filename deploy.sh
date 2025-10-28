#!/bin/bash

echo "📦 کپی کردن CSS از ledger به static..."

cp ledger/static/css/styles.css static/css/styles.css

if [ $? -eq 0 ]; then
    echo "✅ کپی با موفقیت انجام شد."
    echo "ℹ️ حالا برو به PythonAnywhere > Web و 'Reload' رو بزن."
else
    echo "❌ خطا در هنگام کپی فایل!"
fi
