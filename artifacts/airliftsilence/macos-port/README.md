# macOS 移植版（替代 Windows 路线的尝试）

> **目的**：如果你不想为了一件小事去开那台 Windows 电脑，这个版本让你**只在这台 Mac 上插上 iPhone** 就能完成。
>
> **它是在原版基础上改的**——保留了全部逃逸逻辑，只替换了「在哪加载 Apple 的两个库」和几处 macOS 适配。
>
> 原版只支持 Windows（按目录找 `AirTrafficHost.dll`），但 macOS 上同样存在 `AirTrafficHost.framework` 与 `CoreFoundation.framework`，**符号完全一致**。

---

## 一、已验证的部分（本机实测，非推断）

| 验证项 | 结果 |
|---|---|
| macOS 27.0.1 (arm64) 上 `AirTrafficHost` 框架 | ✅ 需要的 **9/9** 符号全部可用 |
| macOS 27.0.1 (arm64) 上 `CoreFoundation` | ✅ 需要的 **8/8** 符号全部可用 |
| `AppleCF()` 实例化 | ✅ 两个框架正确加载 |
| 实际调用 CoreFoundation 函数 | ✅ 字符串往返正确 |
| CFPropertyList 往返转换 | ✅ `dict → CF → dict` 完全一致 |
| `usbmux` 设备枚举链路 | ✅ macOS 上正常（当前返回 0 台，因为没插设备） |
| 完整启动链路干跑 | ✅ 走到 `no USB devices found` —— 无设备时的正确行为 |
| 平台分支隔离 | ✅ macOS 路径不会触碰 Windows 专有的 `os.add_dll_directory` |
| 字体适配 | ✅ `PingFang SC` 在本机存在；上游硬编码的 `Microsoft YaHei UI` 不存在 |
| Python 语法 | ✅ `airlift.py` / `airlift_gui.py` 均通过 |

**注意**：**没有插上 iPhone 就真的没法验证的部分**——真正调用 `ATHostConnection*` 那一串需要设备配合。上面验证的是「加载、绑定、调用协议、枚举链路」，不等于「AirTraffic 同步能在 macOS 上跑通」。

---

## 二、改了什么（相对上游）

### 1. `airlift.py` —— 库加载（唯一的实质性改动）

原来：

```python
APPLE_DLL_DIRS = (r"C:\Program Files\...", ...)   # 只找 Windows DLL
...
os.add_dll_directory(d)                            # Windows 专有 API
self.cf = ctypes.CDLL(os.path.join(dll_dir, "CoreFoundation.dll"))
self.at = ctypes.CDLL(os.path.join(dll_dir, "AirTrafficHost.dll"))
```

现在按平台分流：

```python
_MACOS = sys.platform == "darwin"

MACOS_COREFOUNDATION = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
MACOS_AIRTRAFFICHOST_CANDIDATES = (
    "/System/Library/PrivateFrameworks/AirTrafficHost.framework/Versions/Current/AirTrafficHost",
    "/System/Library/PrivateFrameworks/AirTrafficHost.framework/AirTrafficHost",
)
```

- CoreFoundation 用 `ctypes.util.find_library("CoreFoundation")` 加载——**必须这样**，因为它在 dyld 共享缓存里，`os.path.isfile()` 对它不可靠
- AirTrafficHost 按候选路径依次尝试
- **Windows 的加载逻辑完整保留**，同一份代码在 Windows 上行为不变
- **所有 ctypes 签名绑定一行未改**——CoreFoundation / AirTrafficHost 的 C API 在两个平台上同名同签名

另外这个文件**已经包含上一轮那个设备识别 bug 的修复**（`product_type` 兼容）。

### 2. `airlift_gui.py` —— 两处 macOS 适配

| 问题 | 上游写法 | 改法 |
|---|---|---|
| 字体 | 硬编码 `"Microsoft YaHei UI"`，macOS 上不存在，Tk 会静默回退到可能不显示中文的字体 | `ui_font()` 按平台选：macOS 用 `PingFang SC`，Windows 用原字体 |
| 备份目录 | `%LOCALAPPDATA%` 在 macOS 上不存在，`Path.home()` 兜底会把备份写到 `~/AirliftSilence`（主目录根下） | macOS 上用 `~/Library/Application Support/AirliftSilence/backup`（规范位置） |

Windows 行为不变。

### 3. `silent/` —— 未改动

仍是 Windows 版自带的那两个静音件（格式与真机不匹配，**不要用**）。请用 `../silent-ios-format/` 那套，见下方用法。

---

## 三、怎么用

### 准备

```sh
python3 -m venv .venv
.venv/bin/pip install pymobiledevice3
```

### 第 1 步：零风险体检（先做这个）

```sh
.venv/bin/python ../设备体检.py scan
```

只读 Media 目录，不触发 exploit。若报告发现 `airlift-replaced-*`，先按操作手册第四章抢救出来。

### 第 2 步：dump 原件（先读后写，不可跳过）

```sh
.venv/bin/python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf backup-StopDisclosure.caf --logging
.venv/bin/python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a backup-StartDisclosureWithTone.m4a --logging
```

### 第 3 步：比对哈希（决定能否继续）

```sh
shasum -a 256 backup-StopDisclosure.caf
```

对照 `../silent-ios-format/original-StopDisclosure.caf` 的哈希：

- **一致** → 直接用 `../silent-ios-format/` 那套静音件
- **不一致** → 用 `../静音件生成.sh` 按你设备的实际格式重新生成（这个脚本也在 Mac 上跑）

### 第 4 步：替换

```sh
.venv/bin/python airlift.py replace /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf ../silent-ios-format/silent-StopDisclosure.caf --backup device-backup-StopDisclosure.caf --logging
.venv/bin/python airlift.py replace /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a ../silent-ios-format/silent-StartDisclosureWithTone.m4a --backup device-backup-StartDisclosureWithTone.m4a --logging
```

**每次都要检查 JSON 的 `previousSize` 不为 `null`。**

### 第 5 步：实测

打电话开始/结束录音，听提示音；然后**重启手机再测一次**。

---

## 四、如果 macOS 路线失败

这完全可能——**真正调用 AirTraffic 的那几步在 macOS 上从未被验证过**。失败的表现通常是 `device rejected sync` 或超时。

**失败就回退到 Windows 路线**（那才是作者验证过的环境）：

- `../预检.bat` → `../source-patched/` → `../silent-ios-format/`
- 见 [AirliftSilence-Windows操作手册](../../../docs/AirliftSilence-Windows操作手册.md)

两条路线可以并存，互不影响：**macOS 版只改了库加载，没有改动设备上的任何东西**。macOS 试失败不会让你失去 Windows 那条路。

---

## 五、风险与诚实声明

| 项 | 说明 |
|---|---|
| 🔴 **AT 调用未验证** | 加载和绑定都验证了，但 `ATHostConnection*` 这些函数在 macOS 上的**实际行为**是否与 Windows 一致，**只有插上设备才知道**。Windows 版是作者端到端验证过的，macOS 版不是。 |
| 🟠 **作者未支持 macOS** | 上游明确只支持 Windows，理由写的是「漏洞需要 `AirTrafficHost.dll`」——这个理由只对那个 Windows 移植版成立，macOS 上框架是存在的（本机已验证）。但这意味着出了 macOS 特有问题是没人踩过的路。 |
| 🟠 **可能白试一场** | 如果 macOS 上 AirTraffic 的行为有差异，你会浪费一次尝试的时间。不过插上设备跑第一条 `read` 命令就能知道结果，成本不高。 |
| 🟢 **对设备无副作用** | 库加载失败发生在本机，设备收不到任何请求。只有走到 `_atc_sync` 才会真的碰设备。 |

**建议**：既然插上手机的功夫是一样的，**可以先试 macOS 版**——第一条 `read` 命令跑通就说明这条路成立；跑不通再换 Windows，损失很小。

---

*基于 `YiHoooong/AirliftSilence` v1.0.0 的 `airlift.py` 与 `airlift_gui.py` 修改。*
*对应上游 pin 的 `DahanGuy/airlift-windows` 代码血统。*
