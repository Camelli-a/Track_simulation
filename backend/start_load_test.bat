@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   轨道模拟系统无硬件压测工具
echo ========================================
echo.

:menu
echo 请选择操作:
echo 1. 启动后端服务（模拟模式）
echo 2. 运行简单压测
echo 3. 运行高级压测
echo 4. 运行无硬件压测
echo 5. 恢复原配置
echo 6. 退出
echo.

set /p choice=请输入选择 (1-6): 

if "%choice%"=="1" goto start_server
if "%choice%"=="2" goto simple_test
if "%choice%"=="3" goto advanced_test
if "%choice%"=="4" goto no_hardware_test
if "%choice%"=="5" goto restore_config
if "%choice%"=="6" goto exit
echo 无效选择
goto menu

:start_server
echo.
echo 正在切换到模拟配置...
copy .env.mock .env /Y >nul
echo ✓ 已切换到模拟配置
echo.
echo 正在启动后端服务...
echo 按 Ctrl+C 停止服务
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
goto menu

:simple_test
echo.
echo 正在运行简单压测...
python load_test_simple.py
pause
goto menu

:advanced_test
echo.
echo 正在运行高级压测...
python load_test_advanced.py
pause
goto menu

:no_hardware_test
echo.
echo 正在运行无硬件压测...
python load_test_no_hardware.py
pause
goto menu

:restore_config
echo.
echo 正在恢复原配置...
if exist .env.original (
    copy .env.original .env /Y >nul
    echo ✓ 已恢复原配置
) else (
    echo ! 未找到原始配置备份
)
pause
goto menu

:exit
echo.
echo 退出压测工具
exit /b 0