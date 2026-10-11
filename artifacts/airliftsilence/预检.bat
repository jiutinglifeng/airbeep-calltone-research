@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "BADFILES="
set "DLLFOUND="
set "PYMISSING="
set "PD3MISSING="

echo ============================================================
echo  AirliftSilence 预检（写操作之前运行）
echo  目标设备：iPhone 18 Pro Max / iOS 27.0.1 (24A446)
echo ============================================================
echo.

REM ---------------------------------------------------------------
echo [1/5] 文件完整性校验（防拷贝损坏）
echo ---------------------------------------------------------------
call :checkfile "AirliftSilence-v1.0.0.exe"                              "3bb09e07d22660b9f98c3dd12cedd177af5802040d8c7aee52d89974e1de6e5e"
call :checkfile "silent-ios-format\silent-StartDisclosureWithTone.m4a"   "5f989711c74b60ad054d822d1202f52ebac37065cff9f7939c868644b8eaf177"
call :checkfile "silent-ios-format\silent-StopDisclosure.caf"            "067b9b814203c67b5eed4855c353c044dee5d34081beaeab6e8224c6d850e950"
call :checkfile "silent-ios-format\original-StartDisclosureWithTone.m4a" "e4ff9f8a0cfa1994321492c509bcd166e5ef6d341e9caa2b41631ef64eca3b47"
call :checkfile "silent-ios-format\original-StopDisclosure.caf"          "6b9dd7f8a267a79b1ee2184e52d447c541f4bc76830424373a7bdf2fff9ef7be"
call :checkfile "src\airlift.py"                                         "d15d59a0d86b4a6c3d8606eb50798fe30f77dbd72c1bb5cf2de1e53e3d8bb6e0"
call :checkfile "src\airlift_gui.py"                                     "cadfc463a646c666db0816e5da306402d14fde4798d933cfe82fcd47cfb5e88f"
call :checkfile "src\silent\StartDisclosureWithTone.m4a"                 "efcde5b82b4ec6e9716e34622350dfed288142cbe4692d216141f347c8369580"
call :checkfile "src\silent\StopDisclosure.caf"                          "c8ccb2c43e24cdd8ffb49bc33b6c523003158685d312cbb2c835d81ecbe8349e"

if defined BADFILES (
  echo.
  echo   [!] 有文件缺失或不匹配。如果是从网盘/GitHub 拷来的，请重新拷贝。
) else (
  echo   ^>^> 全部 9 个文件校验通过
)
echo.

REM ---------------------------------------------------------------
echo [2/5] Apple 驱动检查（漏洞依赖 AirTrafficHost.dll）
echo ---------------------------------------------------------------
for %%D in (
  "C:\Program Files\Common Files\Apple\Mobile Device Support"
  "C:\Program Files (x86)\Common Files\Apple\Mobile Device Support"
  "C:\Program Files\Common Files\Apple\Apple Application Support"
  "C:\Program Files (x86)\Common Files\Apple\Apple Application Support"
  "C:\Program Files\iTunes"
  "C:\Program Files (x86)\iTunes"
) do (
  if exist "%%~D\AirTrafficHost.dll" (
    if not defined DLLFOUND (
      echo   [OK]   找到 AirTrafficHost.dll
      echo          %%~D
      set "DLLFOUND=1"
    )
  )
)
if not defined DLLFOUND (
  echo   [缺失] 没找到 AirTrafficHost.dll
  echo.
  echo          请先安装 64 位 iTunes 或 Apple Mobile Device Support：
  echo          https://support.apple.com/downloads/itunes
  echo          装完请重启电脑。
  echo.
  echo          ^>^> 这是硬性依赖，缺失则整个方案无法运行。
)
echo.

REM ---------------------------------------------------------------
echo [3/5] Python 环境检查
echo ---------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
  echo   [缺失] 没找到 python
  echo.
  echo          命令行方式需要 Python。安装时务必勾选
  echo          "Add python.exe to PATH"。
  echo          下载：https://www.python.org/downloads/windows/
  set "PYMISSING=1"
) else (
  for /f "delims=" %%V in ('python --version 2^>^&1') do echo   [OK]   %%V
  python -c "import pymobiledevice3" >nul 2>&1
  if errorlevel 1 (
    echo   [待装] 缺少 pymobiledevice3，请运行：
    echo            pip install pymobiledevice3
    set "PD3MISSING=1"
  ) else (
    echo   [OK]   pymobiledevice3 已安装
  )
)
echo.

REM ---------------------------------------------------------------
echo [4/5] iPhone 连接检查
echo ---------------------------------------------------------------
powershell -NoProfile -Command "$d = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'Apple iPhone|Apple Mobile Device' }; if ($d) { $d | ForEach-Object { Write-Host ('  [OK]   ' + $_.FriendlyName + '  [' + $_.Status + ']') } } else { Write-Host '  [未检测到] 没找到 iPhone'; Write-Host ''; Write-Host '  请检查：'; Write-Host '    1. 数据线是否支持数据传输（部分线只能充电）'; Write-Host '    2. iPhone 是否已解锁'; Write-Host '    3. 是否点了「信任此电脑」'; Write-Host '    4. 是否插在 USB 3 口而非扩展坞/Hub'" 2>nul
echo.

REM ---------------------------------------------------------------
echo [5/5] 人工确认项
echo ---------------------------------------------------------------
echo   [!] 请确认 iPhone 上「设置 ^> 通用 ^> 软件更新 ^> 自动更新」
echo       已经全部关闭。
echo.
echo       本漏洞在 iOS 27.2 beta 3 已被 Apple 修补，一旦升级即永久失效。
echo       这是本项目最容易前功尽弃的地方。
echo.

REM ---------------------------------------------------------------
echo ============================================================
echo  预检总结
echo ============================================================
if defined BADFILES   echo   [失败] 有文件缺失或哈希不匹配  -^> !BADFILES!
if not defined DLLFOUND echo   [失败] 缺少 AirTrafficHost.dll
if defined PYMISSING  echo   [失败] 缺少 Python
if defined PD3MISSING echo   [待办] 需要 pip install pymobiledevice3
echo.
if defined BADFILES goto :blocked
if not defined DLLFOUND goto :blocked
if defined PYMISSING goto :blocked

echo   ^>^> 可以继续。
echo.
if defined PD3MISSING (
  echo   先装依赖：  pip install pymobiledevice3
  echo.
)
echo   第 1 步：先做一次零风险的设备体检（只读，不触发 exploit）
echo.
echo     python 设备体检.py scan
echo.
echo     如果它报告发现 airlift-replaced-* 或 airlift-recovered-*，
echo     先按操作手册第四章把它抢救出来，再往下走。
echo.
echo   第 2 步：dump 原件（不要先写！）
echo.
echo     cd src
echo     python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf backup-StopDisclosure.caf --logging
echo     python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a backup-StartDisclosureWithTone.m4a --logging
echo.
echo   第 3 步：比对格式是否匹配（决定能否继续）
echo.
echo     certutil -hashfile backup-StopDisclosure.caf SHA256
echo     期望值 6b9dd7f8a267a79b1ee2184e52d447c541f4bc76830424373a7bdf2fff9ef7be
echo.
echo   一致   -^> 可以用 silent-ios-format 那套静音件
echo   不一致 -^> 停下，用 dump 出来的原件的格式和时长重新生成静音件
echo.
pause
exit /b 0

:blocked
echo   ^>^> 存在失败项，请先解决再继续。
echo.
echo   不要在有失败项的情况下运行 replace 命令。
echo.
pause
exit /b 1

REM ===============================================================
REM 子过程：校验单个文件 SHA256
REM ===============================================================
:checkfile
set "F=%~1"
set "EXPECT=%~2"
if not exist "%F%" (
  echo   [缺失] %F%
  set "BADFILES=!BADFILES! %F%"
  goto :eof
)
set "ACTUAL="
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%F%" SHA256 2^>nul') do (
  if not defined ACTUAL (
    set "LINE=%%H"
    set "LINE=!LINE: =!"
    if not "!LINE!"=="" set "ACTUAL=!LINE!"
  )
)
if /i "!ACTUAL!"=="%EXPECT%" (
  echo   [OK]   %F%
) else (
  echo   [不匹配] %F%
  echo            期望 %EXPECT%
  echo            实际 !ACTUAL!
  set "BADFILES=!BADFILES! %F%"
)
goto :eof
