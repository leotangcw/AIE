@echo off
REM ===========================================
REM AIE 本地测试脚本 (Windows)
REM 在推送代码前运行此脚本进行本地 CI 检查
REM ===========================================

setlocal enabledelayedexpansion

REM 颜色定义 (Windows 10+)
set "BLUE=[0;34m"
set "GREEN=[0;32m"
set "YELLOW=[1;33m"
set "RED=[0;31m"
set "NC=[0m"

REM 统计
set TESTS_PASSED=0
set TESTS_FAILED=0

echo %BLUE%╔════════════════════════════════════════╗%NC%
echo %BLUE%║   AIE 本地 CI 检查                      %NC%
echo %BLUE%╚════════════════════════════════════════╝%NC%
echo.

REM ===========================================
REM 1. Python 代码风格检查
REM ===========================================
echo %YELLOW%[1/5] Python 代码风格检查%NC%

where flake8 >nul 2>&1
if %errorlevel% equ 0 (
    flake8 backend --config=.flake8 --statistics
    if %errorlevel% equ 0 (
        echo %GREEN%✓ flake8 检查通过%NC%
        set /a TESTS_PASSED+=1
    ) else (
        echo %RED%✗ flake8 检查失败%NC%
        set /a TESTS_FAILED+=1
    )
) else (
    echo %YELLOW%⚠ flake8 未安装，跳过检查%NC%
    echo   安装：pip install flake8
)

echo.

REM ===========================================
REM 2. Python 格式化检查
REM ===========================================
echo %YELLOW%[2/5] Python 格式化检查%NC%

where black >nul 2>&1
if %errorlevel% equ 0 (
    black --check backend\ 2>nul
    if %errorlevel% equ 0 (
        echo %GREEN%✓ black 格式化检查通过%NC%
        set /a TESTS_PASSED+=1
    ) else (
        echo %RED%✗ black 格式化检查失败%NC%
        echo   修复：black backend\
        set /a TESTS_FAILED+=1
    )
) else (
    echo %YELLOW%⚠ black 未安装，跳过检查%NC%
    echo   安装：pip install black
)

echo.

REM ===========================================
REM 3. 导入排序检查
REM ===========================================
echo %YELLOW%[3/5] 导入排序检查%NC%

where isort >nul 2>&1
if %errorlevel% equ 0 (
    isort --check-only backend\ 2>nul
    if %errorlevel% equ 0 (
        echo %GREEN%✓ isort 导入排序检查通过%NC%
        set /a TESTS_PASSED+=1
    ) else (
        echo %RED%✗ isort 导入排序检查失败%NC%
        echo   修复：isort backend\
        set /a TESTS_FAILED+=1
    )
) else (
    echo %YELLOW%⚠ isort 未安装，跳过检查%NC%
    echo   安装：pip install isort
)

echo.

REM ===========================================
REM 4. 单元测试
REM ===========================================
echo %YELLOW%[4/5] 运行单元测试%NC%

where pytest >nul 2>&1
if %errorlevel% equ 0 (
    pytest backend\tests\ -v --tb=short
    if %errorlevel% equ 0 (
        echo %GREEN%✓ 单元测试通过%NC%
        set /a TESTS_PASSED+=1
    ) else (
        echo %YELLOW%⚠ 单元测试失败或无测试文件%NC%
    )
) else (
    echo %YELLOW%⚠ pytest 未安装，跳过测试%NC%
    echo   安装：pip install pytest pytest-asyncio
)

echo.

REM ===========================================
REM 5. 前端检查
REM ===========================================
echo %YELLOW%[5/5] 前端代码检查%NC%

if exist "frontend" (
    cd frontend

    where npm >nul 2>&1
    if %errorlevel% equ 0 (
        if exist "package.json" (
            REM 安装依赖
            if not exist "node_modules" (
                echo   安装前端依赖...
                npm ci --silent
            )

            REM ESLint 检查
            npm run lint >nul 2>&1
            if %errorlevel% equ 0 (
                echo %GREEN%✓ ESLint 检查通过%NC%
                set /a TESTS_PASSED+=1
            ) else (
                echo %YELLOW%⚠ ESLint 检查未通过或未配置%NC%
            )

            REM TypeScript 检查
            npm run type-check >nul 2>&1
            if %errorlevel% equ 0 (
                echo %GREEN%✓ TypeScript 检查通过%NC%
                set /a TESTS_PASSED+=1
            ) else (
                echo %YELLOW%⚠ TypeScript 检查未通过或未配置%NC%
            )

            REM 构建检查
            npm run build >nul 2>&1
            if %errorlevel% equ 0 (
                echo %GREEN%✓ 前端构建成功%NC%
                set /a TESTS_PASSED+=1
            ) else (
                echo %RED%✗ 前端构建失败%NC%
                set /a TESTS_FAILED+=1
            )
        )
    ) else (
        echo %YELLOW%⚠ npm 未安装，跳过前端检查%NC%
    )

    cd ..
) else (
    echo %YELLOW%⚠ frontend 目录不存在，跳过检查%NC%
)

echo.

REM ===========================================
REM 总结
REM ===========================================
echo %BLUE%╔════════════════════════════════════════╗%NC%
echo %BLUE%║              检查总结                  %NC%
echo %BLUE%╚════════════════════════════════════════╝%NC%
echo.
echo 通过：%GREEN%%TESTS_PASSED%%NC%
echo 失败：%RED%%TESTS_FAILED%%NC%
echo.

if %TESTS_FAILED% gtr 0 (
    echo %RED%❌ 部分检查失败，请修复后再推送代码%NC%
    exit /b 1
) else (
    echo %GREEN%✅ 所有检查通过，可以推送代码！%NC%
    exit /b 0
)
