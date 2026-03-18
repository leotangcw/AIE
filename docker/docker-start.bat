@echo off
REM ===========================================
REM AIE Docker 一键启动脚本 (Windows)
REM ===========================================

setlocal enabledelayedexpansion

REM 默认配置
set PROFILE=dev
set ACTION=up
set ENV_FILE=.env.docker

REM ===========================================
REM 帮助信息
REM ===========================================
:show_help
echo 🐳 AIE Docker 一键启动脚本
echo.
echo 用法：%~nx0 [选项]
echo.
echo 选项:
echo     -p, --profile     环境配置 (ci^|dev^|prod)  默认：dev
echo     -a, --action      操作类型 (up^|down^|build^|restart)  默认：up
echo     -e, --env         环境变量文件路径
echo     -h, --help        显示帮助信息
echo.
echo 示例:
echo     %~nx0 -p dev -a up    启动开发环境
echo     %~nx0 -p ci -a up     启动 CI 环境
echo     %~nx0 -p prod -a up   启动生产环境
echo     %~nx0 -a build        构建镜像
echo     %~nx0 -a down         停止所有服务
echo.
goto :end_help

:parse_args
if "%~1"=="" goto :run
if /i "%~1"=="-p" (
    set PROFILE=%~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--profile" (
    set PROFILE=%~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="-a" (
    set ACTION=%~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--action" (
    set ACTION=%~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="-e" (
    set ENV_FILE=%~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--env" (
    set ENV_FILE=%~2
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help

echo ❌ 未知选项：%~1
goto :show_help

:end_help
exit /b 0

:run
REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR:~0,-1%
cd /d "%PROJECT_ROOT%"

echo.
echo 🔍 检查环境...

REM 检查 Docker
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 未安装
    exit /b 1
)
echo ✓ Docker 已安装

REM 检查 Docker Compose
where docker-compose >nul 2>&1
if %errorlevel% equ 0 (
    set COMPOSE_CMD=docker-compose
) else (
    docker compose version >nul 2>&1
    if %errorlevel% equ 0 (
        set COMPOSE_CMD=docker compose
    ) else (
        echo ❌ Docker Compose 未安装
        exit /b 1
    )
)
echo ✓ Docker Compose 已安装

REM 加载环境变量
if exist "%ENV_FILE%" (
    echo 📁 加载环境变量：%ENV_FILE%
)

echo.
echo ╔════════════════════════════════════════╗
echo ║   AIE Docker %PROFILE% 环境                    ║
echo ╚════════════════════════════════════════╝
echo.

if /i "%ACTION%"=="up" (
    echo 🚀 启动 %PROFILE% 环境...
    if "%PROFILE%"=="ci" (
        %COMPOSE_CMD% --profile ci up -d
    ) else if "%PROFILE%"=="dev" (
        %COMPOSE_CMD% --profile dev up -d
    ) else if "%PROFILE%"=="prod" (
        %COMPOSE_CMD% --profile prod up -d --build
    )
    echo ✅ 服务启动完成!

    echo.
    echo 📊 服务状态：
    %COMPOSE_CMD% ps

    echo.
    if "%PROFILE%"=="dev" (
        echo 🌐 开发环境访问地址：
        echo    前端：http://localhost:3000
        echo    后端 API: http://localhost:8000
        echo    API 文档：http://localhost:8000/docs
    ) else if "%PROFILE%"=="prod" (
        echo 🌐 生产环境访问地址：
        echo    应用：http://localhost
    )
) else if /i "%ACTION%"=="down" (
    echo 🛑 停止所有服务...
    %COMPOSE_CMD% down
    echo ✅ 服务已停止
) else if /i "%ACTION%"=="build" (
    echo 🔨 构建镜像...
    %COMPOSE_CMD% build
    echo ✅ 镜像构建完成
) else if /i "%ACTION%"=="restart" (
    echo 🔄 重启服务...
    %COMPOSE_CMD% restart
    echo ✅ 服务已重启
) else if /i "%ACTION%"=="test" (
    echo 🧪 运行 CI 测试...
    %COMPOSE_CMD% --profile ci up --abort-on-container-exit ci-test
) else (
    echo ❌ 未知操作：%ACTION%
    goto :show_help
)

echo.
