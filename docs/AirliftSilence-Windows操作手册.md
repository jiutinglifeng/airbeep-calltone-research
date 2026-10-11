# AirliftSilence 操作手册（Windows 侧）

> 目标设备：iPhone 18 Pro Max / **iOS 27.0.1 (24A446)**
> 执行环境：**Intel/AMD 的 Windows 电脑**（ARM Windows 不可用，见附录 A）
> 编写时间：2026-10-11

---

## 一、这套方案为什么优于 AirBeep

| 麻烦 | AirBeep | AirliftSilence（本方案） |
|---|---|---|
| IPA 重签名 | 必须 | **不需要** |
| 免费 Apple ID 的 7 天限制 | 有 | **无关** |
| LocalDevVPN / 回环隧道 | 必需 | **不需要** |
| 美区 Apple ID | 需要 | **不需要** |
| iPhone 上装任何东西 | 要装 App | **什么都不用装** |
| 备份位置 | App 的 Documents（重装即失） | **Windows 电脑本地** |
| 连接方式 | 无线配对 | **一根数据线** |

连接走的是 iTunes 同款的 USB lockdown 服务，不需要配对文件、不需要 VPN、不需要信任之外任何授权。

---

## 二、材料清单

全部在 `artifacts/airliftsilence/`：

| 路径 | 说明 |
|---|---|
| **`预检.bat`** | ✅ **第一件事就双击运行它**（校验哈希、驱动、Python、设备连接） |
| **`设备体检.py`** | ✅ **只读救援工具**，写操作前后都该跑（详见第四章） |
| `AirliftSilence-v1.0.0.exe` | 图形界面主程序（37 MB，官方 v1.0.0） |
| `src/airlift.py` | 源码：命令行版（**推荐用它，日志更全，便于排障**） |
| `src/airlift_gui.py` | 源码：图形界面版 |
| `src/README.zh-CN.md` | 作者原版中文说明 |
| `src/silent/` | ⚠️ **Windows 版自带静音件（格式可能不匹配，不要用）** |
| `silent-ios-format/` | ✅ **推荐使用的静音件 + 作者 dump 的真机原件** |

> ⚠️ `预检.bat` 是在 macOS 上写的，**未在真实 Windows 上执行验证过**。已做的验证只有内嵌哈希与源文件一致、标签齐全、括号配对。若它行为异常（报错、计数不对），**不要相信它的结论**，改用 `certutil -hashfile <文件> SHA256` 手工逐个比对。

### 两套静音件的区别（关键）

| 文件 | Windows 版自带 | ✅ iOS 格式版（推荐） | 真机原件 |
|---|---|---|---|
| `StartDisclosureWithTone.m4a` | AAC 44.1k **1.8340 s** | AAC 44.1k **1.6718 s** | AAC 44.1k 1.6186 s |
| `StopDisclosure.caf` | **PCM** 48k **1.7697 s** | **Opus** 48k **1.9400 s** | **Opus** 48k 1.9200 s |

**Stop 提示音的问题最大**：真机上是 Opus，Windows 版却写 PCM，而且短了 150 ms。作者在自己的 iOS 仓库里配的那套（`silent-ios-format/`）编码格式与真机一致，时长也只差 20 ms，**所以用这一套**。

---

## 三、操作步骤

### 步骤 0：Windows 侧准备

1. 安装 **64 位 iTunes** 或 **Apple Mobile Device Support**（必须，漏洞依赖 `AirTrafficHost.dll`）
2. 把 `artifacts/airliftsilence/` 整个目录拷到 Windows
3. **双击运行 `预检.bat`** ← 🔴 **先做这一步**
   - 校验 9 个文件的 SHA256（防止拷贝损坏）
   - 检查 `AirTrafficHost.dll` / Python / `pymobiledevice3` / iPhone 连接
   - 有失败项时会阻止你继续，并打印该做什么
4. ⚠️ exe **没有代码签名**，Windows Defender / SmartScreen 会拦。需要加白名单或临时关闭实时保护。源码运行可以避免这一步

### 步骤 1：连接设备

1. iPhone 用数据线连 Windows
2. **解锁屏幕**
3. 弹出「信任此电脑」→ 点信任
4. iPhone 上「设置 › 隐私与安全性 › 开发者模式」**无需打开**（本方案不需要）

> ⏰ **时间窗提醒**：iOS 27.2 正式版预计 **2026-10-26 那一周**发布，届时本方案永久失效。请确认 iPhone 的「自动更新」已全部关闭，且不要点任何更新提示。

### 步骤 2：检查设备（先跑这个）

**推荐用源码方式，日志更全：**

```cmd
pip install pymobiledevice3
cd src
python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf device-StopDisclosure.caf --logging
```

> 预期会打印 `⚠ 这个 iOS 版本没有在作者的测试列表里`——**这是正常的**，作者忘了把 `24A446` 加进代码白名单，但 README 明确写了 24A446 已验证。这只是警告，不会阻止操作。

### 步骤 3：先 dump 原件存档（重要）

在替换之前，**务必先把当前设备上的两个文件读出来存好**。这是你唯一的独立保险。

**但先做一次零风险的体检：**

```cmd
python 设备体检.py scan
```

它只读 Media 目录、不触发 exploit。**如果报告发现 `airlift-replaced-*` 或 `airlift-recovered-*`，先按第四章把它抢救出来再往下走**——那可能是之前中断留下的原件。

**确认干净后，再 dump 两个原件：**

```cmd
python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf backup-StopDisclosure.caf --logging
python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a backup-StartDisclosureWithTone.m4a --logging
```

**`read` 是往返操作**：它把文件移到 Media、读出、再写回原位。成功时文件回到原样，所以这一步**同时完成了备份和管道验证**。

**读完立刻做的两件事：**

1. **对比格式**：把 dump 出来的文件和 `silent-ios-format/original-*` 用 `shasum`/`certutil` 对比。
   - 如果 `backup-StopDisclosure.caf` 与 `original-StopDisclosure.caf` **哈希一致** → 你的设备音频与作者 dump 的完全一样，`silent-ios-format/` 那套可以放心用
   - 如果**不一致** → 说明你的系统版本音频有差异，**先停下来**，把 dump 出来的原件保管好，用它的格式和时长去重新生成静音件再用
2. **把 dump 出来的原件复制到 U 盘 / 云盘**，不要只留在 Windows 上

### 步骤 4：替换为静音

用 Windows 版自带的「去除提示音」按钮会写入**格式不匹配的 PCM 静音件**，所以改用命令行显式指定正确的文件：

```cmd
python airlift.py replace /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf ..\silent-ios-format\silent-StopDisclosure.caf --backup ..\silent-ios-format\device-backup-StopDisclosure.caf --logging
```

```cmd
python airlift.py replace /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a ..\silent-ios-format\silent-StartDisclosureWithTone.m4a --backup ..\silent-ios-format\device-backup-StartDisclosureWithTone.m4a --logging
```

**每次替换约 2–4 分钟，全程保持解锁 + 连着数据线。**

#### 🔴 替换后必须检查输出（这一步不能跳过）

命令结束时工具会打印一行 JSON。**必须确认 `previousSize` 是一个具体数字、而不是 `null`：**

```json
{"ok": true, "replaced": "...", "size": 1399, "previousSize": 44325, "backup": "...\\device-backup-StopDisclosure.caf"}
```

| 输出 | 含义 | 该做什么 |
|---|---|---|
| `previousSize` 是数字，且 `backup` 指向的**文件确实存在** | ✅ 原件已成功读回并备份 | 继续下一步 |
| `previousSize: null` / `backup: null` | 🔴 **原件没能读回来**，它被留在了设备的 Media 目录里（`airlift-replaced-<token>`） | **立刻停止后面的步骤**，按第四章情况 A 把它救回本地 |

**两个文件都替换完后，立刻把 `device-backup-*` 复制到 U 盘或云盘。** 这份备份在 Windows 电脑上，是比工具内置备份更可靠的独立副本。

### 步骤 5：实测

1. 打一通电话，**开始录音** → 听是否还有提示音
2. **结束录音** → 听是否还有提示音
3. **重启手机，再测一次**（见第六章"重启失效"风险）

---

## 四、如果中途失败怎么救

> 📋 **出错时先查 [失败签名对照表](失败签名对照表.md)** —— 它把 `airlift.py` 的全部错误串映射到具体动作。

这套机制的失败模式只有一种：**原件被移到 Media 后没被写回**，表现为目标路径缺失文件。**不会变砖**——它只是移动和写入文件，不刷固件、不动系统分区。

**先记住一个关键认知**：`read` 和 `replace` **都不是只读操作**，两者都要先把目标文件移动到 Media。区别只在失败后目标里剩什么：

| 操作 | 失败后目标里剩下 | 原件位置 |
|---|---|---|
| `read` | **空**（CallServices 缺文件） | Media 的 `airlift-recovered-<token>` |
| `replace` | **静音版**（可用） | Media 的 `airlift-replaced-<token>` |

**两种情况下原件都还在 Media 里，都能用 `设备体检.py` 救回来。**

### 🔴 首选方法：用 `设备体检.py`（只读，已测试）

**为什么它能找到原件**：`airlift.py` 的 `_validate_path()` 只禁止写 `/var/mobile/Media`——因为那个目录属于**普通 AFC**，不需要逃逸就能直接读。而失败时原件恰好被留在那里。**所以需要检查的地方正好是可以安全读取的地方。**

```cmd
python 设备体检.py scan
```

输出会列出所有 `airlift-*` 残留，标出哪些可能是原件、给出大小与 SHA256，**并直接打印该执行的抢救命令**：

```cmd
python 设备体检.py pull /var/mobile/Media/airlift-replaced-XXX rescued.bin
```

抢救后，把打印出的 SHA256 与已知原件哈希（见附录 B）比对。**匹配就说明找回了唯一的一份原件，立刻复制到 U 盘。**

> 这个脚本**只读**，跑多少次都不改动设备。已用模拟设备跑通 5 个场景（含字节一致性校验），但仍需真机验证端到端行为。

### 情况 A：`replace` 报错，原件停在 Media

日志里会出现 `airlift-replaced-<token>` 这个文件名。用 AFC 把它拉到本地：

```cmd
python -c "import asyncio; from pymobiledevice3.lockdown import create_using_usbmux; from pymobiledevice3.services.afc import AfcService; async def m():
    ld = await create_using_usbmux()
    afc = AfcService(lockdown=ld)
    await afc.connect()
    data = await afc.get_file_contents('/var/mobile/Media/airlift-replaced-XXX')
    open('rescued.caf','wb').write(data)
asyncio.run(m())"
```

拿到字节后，此时目标路径是空的，用 `write` 正好适用：

```cmd
python airlift.py write /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf rescued.caf --logging
```

### 情况 B：`read` 报错 `could not read`

同样地，原件会留在 Media。按情况 A 的方法救回。

### 情况 C：工具自带的备份丢了

如果你按步骤 3 做了独立 dump 并复制到了 U 盘，直接用那份：

```cmd
python airlift.py write <目标路径> <你的备份文件> --logging
```

---

## 五、项目背景（供排障参考）

- **原理**：AirTraffic / ATAirlock 沙盒逃逸，与 AirBeep 同源
- **入口**：经典 USB lockdown + `AirTrafficHost.dll`（不是 AirBeep 那条 RSD shim 隧道）
- **Grappa 修复**：iOS 27.0.1 上 airlift 系工具集体失效（设备报 `Grappa session could not be established`），本项目通过注入 10 个预生成的 Grappa 客户端令牌解决。令牌来自 AirCard-iOS，与 AirBeep 内置的完全相同
- **替换机制**：AirTraffic 的 `moveItemAtPath:` 不允许覆盖已存在文件，所以"替换"= 先把旧文件搬到 Media → 再把新文件写到空出来的原位
- **安全设计**：只有在旧文件被成功读回本地之后才删除 Media 里的副本；读回失败则保留副本

---

## 六、已知风险

| 风险 | 说明 | 应对 |
|---|---|---|
| 🔴 **重启后可能失效** | 作者称 27.0.1 上重启后依然有效，但有一条**第三方报告**（iOS 18.7.8）称替换成功、**重启后提示音回来了** | 重启后必须实测；失效就重跑一次 |
| 🟠 **无第三方复现** | 该仓库 0 issue / 0 PR，`Verified on 27.0.1` 100% 是作者自述 | 步骤 3 的独立 dump 是唯一保险 |
| 🟠 **随时可能被 Apple 修掉** | 漏洞在 iOS 27.2 beta 3 已被修补 | **立刻关闭自动更新** |
| 🟠 **音频资产可能被静默更新** | 作者在 iOS 仓库里承认这些文件被 Apple 的 MobileAsset 静默替换过 | 若某天提示音自己回来了，重跑一遍 |
| 🟡 **`replace` 是新代码** | 上游只验证过"新建文件"，`replace`（覆盖）是本 fork 新增、无第三方复核 | 步骤 3 先跑 `read` 验证管道通不通 |
| 🟡 **exe 无签名** | SmartScreen 会拦，且 37 MB PyInstaller 产物无法逐行审计 | 可改用源码运行（`src/` 里的 `.py` 完全可读） |

---

## 附录 A：为什么必须用 Intel/AMD Windows

Apple Silicon Mac 只能跑 **Windows 11 ARM**。而 iPhone 被 Windows 识别依赖 **Apple Mobile Device USB 驱动（内核态）**，微软规定内核态驱动必须是原生 ARM64，**Apple Mobile Device Support 没有 arm64 版本**（winget 清单里只有 x86/x64）。

→ 在 ARM Windows 上 iPhone 大概率**根本认不到**，工具会直接报 `no USB devices found`。

**所以本方案必须在 Intel/AMD 的 Windows 上执行。**

## 附录 B：关键数据速查

> 全部文件与我们的仓库：**https://github.com/jiutinglifeng/airbeep-calltone-research**
> 推送时用 `git push myrepo main`（`origin` 是上游别人的仓库，不要推）

```
目标文件：
  /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a
  /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf

项目：https://github.com/YiHoooong/AirliftSilence
Release：v1.0.0（唯一版本）

【主程序与源码 SHA256】
AirliftSilence-v1.0.0.exe    3bb09e07d22660b9f98c3dd12cedd177af5802040d8c7aee52d89974e1de6e5e
src/airlift.py               d15d59a0d86b4a6c3d8606eb50798fe30f77dbd72c1bb5cf2de1e53e3d8bb6e0
src/airlift_gui.py           cadfc463a646c666db0816e5da306402d14fde4798d933cfe82fcd47cfb5e88f

【推荐静音件（iOS 格式）SHA256】
silent-StartDisclosureWithTone.m4a  5f989711c74b60ad054d822d1202f52ebac37065cff9f7939c868644b8eaf177
silent-StopDisclosure.caf           067b9b814203c67b5eed4855c353c044dee5d34081beaeab6e8224c6d850e950

【作者 dump 的真机原件 SHA256（用于比对你的设备）】
original-StartDisclosureWithTone.m4a  e4ff9f8a0cfa1994321492c509bcd166e5ef6d341e9caa2b41631ef64eca3b47
original-StopDisclosure.caf           6b9dd7f8a267a79b1ee2184e52d447c541f4bc76830424373a7bdf2fff9ef7be

【⚠️ Windows 自带静音件（不要用）】
src/silent/StartDisclosureWithTone.m4a  efcde5b82b4ec6e9716e34622350dfed288142cbe4692d216141f347c8369580
src/silent/StopDisclosure.caf           c8ccb2c43e24cdd8ffb49bc33b6c523003158685d312cbb2c835d81ecbe8349e

【设备】iPhone 18 Pro Max / iOS 27.0.1 (24A446)

【硬截止】iOS 27.2 正式版预计 2026-10-26 那一周发布，届时方案作废
```
