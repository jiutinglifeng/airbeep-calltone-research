# HANDOFF — 通话录音提示音消除项目

> **给下一个 AI 会话的交接文档。** 请先完整读本文，再动手。
> 本文写于 2026-10-11，用途是让重新开始的会话**零上下文损失**地接上。
>
> **一句话现状**：方案已确定、材料已备齐、操作手册已写完，**尚未在真机上执行任何写操作**。

---

## 零、🔴 先读这里：现在有两条执行路线

原本只有 Windows 路线，2026-10-11 又做出一条 **macOS 路线**。**先决定走哪条：**

| | **路线 M：macOS（新增）** | **路线 W：Windows（作者验证过的）** |
|---|---|---|
| 需要 | 这台 Mac + 数据线 + iPhone | Intel/AMD Windows + 数据线 + iPhone |
| 前提已验证？ | ✅ 库加载/符号绑定/枚举链路（本机实测） | ✅ 作者端到端验证过 27.0.1 |
| 关键未知 | ⚠️ **`ATHostConnection*` 的实际行为未在 macOS 上验证过** | 无（但依赖未 pin，见第五章 bug） |
| 目录 | `artifacts/airliftsilence/macos-port/` | `artifacts/airliftsilence/source-patched/` |
| 说明 | 见该目录下 `README.md` | 见本文第六章 |

**建议**：既然插手机的功夫一样，**先试 macOS**——第一条 `read` 命令跑通就说明成立，跑不通再换 Windows，损失很小。两条路线互不影响（macOS 版只改了本机的库加载，没动设备上任何东西）。

> 下面的章节主要按 **Windows 路线** 写（它更成熟）。走 macOS 时，把命令里的 `python` 换成 `.venv/bin/python`、`cd source-patched` 换成 `cd macos-port`，其余逻辑（先读后写、哈希比对、`previousSize` 检查、救援流程）**完全一样**。

---

## 一、项目目标与设备

| 项 | 值 |
|---|---|
| 目标 | 消除 iPhone 系统通话录音的开始/结束提示音 |
| 设备 | **iPhone 18 Pro Max** |
| 系统 | **iOS 27.0.1 (24A446)** ← 构建号已与用户截图核对确认 |
| 目标文件 1 | `/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a` |
| 目标文件 2 | `/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf` |

用户在中国大陆使用，已明确表示无需讨论法律风险（其判断：录音者本人为通话参与方时合法）。

---

## 二、🔴 最紧急的未完成事项（附时间压力）

**让用户关闭 iPhone 的自动更新。**（设置 › 通用 › 软件更新 › 自动更新 → 全关）

理由：该漏洞在 **iOS 27.2 beta 3 已被 Apple 修补**，一旦升级即永久失效。上游 AirCard-iOS README 原文警告：
> **Do not update past iOS 27.2 beta 2**

### ⏰ 硬截止时间：约 2026-10-26 那一周

据 2026-10-08 报道（[数字今日](https://www.digitaltoday.co.kr/cn/view/112373/apple-ios-27-2-may-launch-in-late-october-existing-iphones-likely-to-skip-ios-27-1)，转引 9to5Mac）：

- **iOS 27.2 正式版预计在 10 月下旬发布，最可能是 10 月 26 日那一周**，且不排除提前
- **现有 iPhone 机型预计会跳过 iOS 27.1**（27.1 仅供 10 月 23 日发布的 iPhone Duo 出厂搭载）
- 也就是说：**用户的下一次系统更新就是 27.2**，而 27.2 正式版必然包含 beta 3 里那个补丁

**距今天（2026-10-11）大约 15 天。** 这是整个项目最硬的约束——不是技术问题，是日历问题。每次会话都先确认这一条。

另外注意：即使关了「自动更新」，iOS 仍可能弹「立即更新」提示或尝试夜间安装。建议同时关闭「软件更新」里的自动下载/安装项，并提醒用户**不要点任何更新提示**。

---

## 三、最终选定的方案

### 结论：用 AirliftSilence（Windows 版）

项目：https://github.com/YiHoooong/AirliftSilence
本地材料：`artifacts/airliftsilence/`

**为什么选它**——它一次性消掉了另外两条路线的全部障碍：

| 麻烦 | AirBeep（iOS 路线） | AirliftSilence（已选定） |
|---|---|---|
| IPA 重签名 | 必须 | **不需要** |
| 免费 Apple ID 的 7 天限制 | 有 | **无关** |
| LocalDevVPN / 回环隧道 | 必需 | **不需要** |
| 美区 Apple ID | 需要 | **不需要** |
| iPhone 上装任何东西 | 要装 App | **什么都不用装** |
| 备份位置 | App 的 Documents（重装即失） | **Windows 电脑本地** |
| 连接方式 | 无线配对 | **一根数据线** |

原理：AirTraffic / ATAirlock 沙盒逃逸，与 AirBeep **同源**，但入口不同——它走**经典 USB lockdown + `AirTrafficHost.dll`**，而不是 AirBeep 那条 RSD shim 隧道。

### 为什么不需要 Grappa 之外的额外处理

iOS 27.0.1 上所有 airlift 系工具都曾因设备报 `Grappa session could not be established. Aborting` 而失效（表现为 `SyncFailed {ErrorCode: 4}`）。AirliftSilence 通过在 `HostInfo` 里注入 10 个预生成的 Grappa 客户端令牌解决。令牌来自 AirCard-iOS，**与 AirBeep 的 `GrappaHelper.m` 里内置的完全相同**（已核对）。

这也解释了为什么 **AirBeep v2.4.0 砍掉了启动时的状态检测**——它没有做 Grappa 修复，读取在 27.0.1 上不稳定。

---

## 四、已排除的路线（不要再走一遍）

| 路线 | 排除原因 |
|---|---|
| **AirBeep（iOS App）** | 需要 未签名 IPA 重签名 + LocalDevVPN 回环隧道；而 LocalDevVPN 自 2025-12-18 起在中国大陆区下架（美区免费在架，需美区 Apple ID）。且**仓库内静态库过期**，新克隆用 Xcode 直接构建会链接失败 |
| **从源码构建 AirBeep** | 必须先跑 `scripts/build-airlift-xcframework.sh` 重建 Rust 静态库，需 Rust + Xcode 27 + 网络；本机（Mac）无 Xcode、无 Rust |
| **上游 airlift（Mac 端 CLI）** | `Makefile` 依赖 `xcrun clang` 和系统私有框架；PoC 只验证过**新建文件**而非覆盖已有文件；且有一份 [iOS 27.0 实机失败报告](https://github.com/0xjohnnydev/airlift/issues/4)（`streaming_zip_conduit` 在 27.x 上被 entitlement-gated，staging 都过不去）。上游项目最后 push 2026-09-15，基本停更 |
| **在 M4 Mac 上跑 ARM Windows 虚拟机** | Apple Mobile Device USB 驱动是**内核态**，微软规定内核态驱动必须原生 ARM64，而 Apple Mobile Device Support **没有 arm64 版本**。iPhone 大概率根本认不到 |
| **AirliftSilence-iOS** | 门槛与 AirBeep 完全同级（需 LocalDevVPN + 配对 + 自签 IPA），无优势 |
| **bl_sbx 系** | 只支持 iOS 18–26.2b1，不覆盖 iOS 27 |
| **`Lumid-Off/AirCard-Windows`** | ⚠️ **曾被误认为备选，实测否掉。** 它是 Rust 原生 Windows 工具、README 明确支持 **iOS 18.0 – 27.0.1**（正是本设备版本），看起来很有希望；但源码里写死的目标路径只有 `Library/Passes/Cards`（钱包卡面）和 `Library/Caches`（锁屏主题），**完全没有 `CallServices` / `Disclosure` / 提示音的任何引用**（已 grep 全部 `.rs` 确认）。它做不了本任务，只做钱包卡面美化 |

---

## 五、材料清单（`artifacts/airliftsilence/`）

| 路径 | 说明 | SHA256 |
|---|---|---|
| **`预检.bat`** | ✅ **在 Windows 上第一件事就运行它**（见下方说明） | 纯文本，无需校验 |
| **`设备体检.py`** | ✅ **写操作前后都该跑**：只读扫描设备 Media 里的残留文件（见下方说明） | 纯文本，无需校验 |
| **`演练-救援流程.py`** | ✅ 用 mock 设备端到端演练「replace 失败 → 体检 → 救援 → 写回」全流程（20 项断言） | 纯文本，无需校验 |
| **`静音件生成.sh`** | ✅ **哈希不匹配时的回退方案**：按设备原件格式生成匹配的静音件（**需在 Mac 上跑**） | 纯文本，无需校验 |
| `AirliftSilence-v1.0.0.exe` | 图形界面主程序，37 MB，PE32+ x86-64，**无 Authenticode 签名** | `3bb09e07d22660b9f98c3dd12cedd177af5802040d8c7aee52d89974e1de6e5e` |
| `src/airlift.py` | ⚠️ **原版有 bug，不要用**（651 行），见下方「🔴 必读」 | `d15d59a0d86b4a6c3d8606eb50798fe30f77dbd72c1bb5cf2de1e53e3d8bb6e0` |
| **`source-patched/`** | ✅ **Windows 路线要用的目录**：`airlift.py`(修补版) + `airlift_gui.py` + `silent/`，自包含。CLI 和 GUI 都受益 | `airlift.py` = `8b068e600b306bac8da982a7736c6017d0314a9c41e46666752c9065a3b44903` |
| `source-patched/airlift-pymobiledevice3-compat.patch` | 修补内容的补丁原文，便于核对 | — |
| **`macos-port/`** | ✅ **macOS 路线要用的目录**（零、路线 M）：在修补版基础上把库加载改成走 macOS framework，另修了字体与备份路径 | 见该目录 `README.md` |
| `macos-port/macos-port.patch` | 相对 `source-patched/` 的改动原文 | — |
| `src/airlift_gui.py` | 图形界面源码（251 行） | `cadfc463a646c666db0816e5da306402d14fde4798d933cfe82fcd47cfb5e88f` |
| `src/README.zh-CN.md` | 作者原版中文说明 | — |
| `src/silent/` | ⚠️ **Windows 版自带静音件，格式不匹配，不要用** | `efcde5b8…` / `c8ccb2c4…` |
| `silent-ios-format/` | ✅ **推荐使用的静音件 + 作者 dump 的真机原件** | 见下表 |

### `预检.bat` 做什么

双击即可（用 `certutil`，不需要 Python）。它检查 5 项：

1. **9 个文件的 SHA256 完整性**——防止从 GitHub / 网盘 / U 盘拷贝过程中损坏
2. **`AirTrafficHost.dll` 是否存在**（漏洞的硬性依赖，缺失则整个方案无法运行）
3. **Python 与 `pymobiledevice3` 是否就绪**
4. **iPhone 是否已被 Windows 识别**（用 `Get-PnpDevice` 查）
5. 提醒人工确认「自动更新已关闭」

有失败项时它会**明确阻止你继续**，并打印下一步该做什么。

> ⚠️ **诚实声明：这个脚本没有在真实 Windows 上执行过。** 它是本轮（2026-10-11）在 macOS 上写的，本机没有 wine/cmd 无法运行验证。已做的验证只有：9 个内嵌哈希逐个与源文件比对一致、标签与 `goto` 目标齐全、括号配对。如果它报错或计数不对，**不要相信它的结论**，直接手工用 `certutil -hashfile <文件> SHA256` 逐个比对，哈希值见本章表格与附录。

### `设备体检.py` 做什么（🔴 本方案最重要的补充工具）

**它是一个只读的救援工具，全程不触发 exploit、不修改设备上任何文件。**

关键洞察：`airlift.py` 的 `_validate_path()` 只禁止写 `/var/mobile/Media`，因为**那个目录是普通 AFC 的管辖范围，不需要逃逸就能直接读**。而 AirTraffic 逃逸的失败模式恰好是「把原件搬到 Media 后没写回」——**所以需要检查的地方正是 Media，而它恰好可以安全读取**。

三个子命令：

```cmd
python 设备体检.py list                        # 列出 Media 中的 airlift 残留
python 设备体检.py scan                        # 识别残留，报告大小、哈希，并给出救援命令
python 设备体检.py pull <路径> <本地文件>       # 把残留文件抢救到本地
```

**为什么它很重要**：`replace` 失败时，原件会以 `airlift-replaced-<token>` 的名字**留在设备的 Media 目录里**。这个文件用普通文件管理器或「文件」App 看不到，而且 **`restore_sounds()` 在没有备份时会直接报错拒绝执行**——GUI 里也没有翻找 Media 的按钮。也就是说，**失败时用户会以为原件的最后一份副本丢了，其实它还在设备里。** 这个脚本用来把它捞出来。

**使用时机**：
1. **写操作之前先跑 `scan`**——若有残留，说明之前有操作中断过，先抢救再继续
2. **`replace` 报错或 `previousSize` 为 null 时立刻跑 `scan`**

**验证状态（比 `预检.bat` 强得多）**：本脚本已用 pymobiledevice3 的**实际安装版本**核对 API 签名（`listdir` / `get_file_contents` / `connect` 三个调用全部存在，且经 `getsource` 确认均为 `async def`），并用**模拟设备对象跑通 5 个场景**：干净设备、发现被移出的原件、staging 目录残留、`pull` 抢救（含字节一致性校验通过）、`pull` 不存在文件（正确返回退出码 1）。语法检查通过。

**救援流程已端到端演练**：`演练-救援流程.py` 用一个会真实施加副作用的 mock 设备，完整走了一遍

```
replace 失败（原件被移出、目标变空）
    → 设备体检.py scan 发现残留
    → 设备体检.py pull 抢救到本地
    → 校验 SHA256 与原件逐字节一致
    → 模拟 airlift.py write 写回设备
    → 再次 scan 确认干净、且另一个文件未被波及
```

**20 项断言全部通过**，不需要真机、不需要 pymobiledevice3。之所以专门做这个演练：救援流程是唯一「只出事时才用、平时练不到」的路径，如果它本身有缺陷，会在最需要它的那一刻才发现。

> 注意：仍需真机才能验证端到端行为（本机未连接 iPhone）。但逻辑分支与 API 契约已验证。

### 🔴 必读：原版 `src/airlift.py` 有一个会让你误判的 bug
**症状**：设备明明连上了、也点了「信任此电脑」，工具却报 `no paired iPhone found`。

**原因**（已在本机用 pymobiledevice3 **11.26.1** 复现确认）：`airlift.py:375` 有一行

```python
pt = ld.product_type or ""
```

但 pymobiledevice3 11.x 的 **lockdown 客户端没有 `product_type` 属性**——`product_type` 只属于 irecv（DFU 恢复模式）子系统。这行抛 `AttributeError`，而它下一行就是

```python
except Exception:
    continue
```

**异常被静默吞掉、每台设备都被跳过**，最后抛出与实际原因毫无关系的 `no paired iPhone found`。

**为什么作者验证通过了你却会踩到**：两个仓库（上游 `DahanGuy/airlift-windows` 和 `YiHoooong/AirliftSilence`）**都没有 pin pymobiledevice3 版本**，README 只写 `pip install pymobiledevice3`。该库在 PyPI 上已有 **700+ 个版本**、迭代极快，属性会随版本漂移。

**所以：用 `source-patched/airlift.py`，不要用 `src/airlift.py`。** 命令改成：

```cmd
cd source-patched
python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf backup-StopDisclosure.caf --logging
```

修补内容只有 `_resolve_device` 里的设备型号探测，改成「属性 → `all_values` → `get_value`」三级兜底，**新旧版本的 pymobiledevice3 都能工作**。

> **已验证**：用假的 lockdown 对象跑修补后的函数，无论客户端有没有 `product_type` 都能正确识别设备；非 iPhone 设备仍被正确跳过。并用 AST 确认修改后的文件里再没有裸的属性访问。补丁原文见 `source-patched/airlift-pymobiledevice3-compat.patch`。

> **📮 可选的贡献**：截至 2026-10-11，上游两个仓库（`DahanGuy/airlift-windows`、`YiHoooong/AirliftSilence`）**都没有任何 issue 提到这个问题**（已用 GitHub 搜索确认，`product_type` 关键词命中 0 条）。如果你在 Windows 上实际踩到了它，可以考虑给作者提个 issue——这属于依赖未 pin 版本导致的 API 漂移，对作者也有价值。修复代码已在 `source-patched/`，可直接引用。当然这不是必须做的，不影响你的目标。

### `静音件生成.sh` 做什么（哈希不匹配时的回退方案）

**触发条件**：操作流程步骤 3 要求把设备原件 dump 下来、与作者 dump 的 `original-*` 比对 SHA256。**如果哈希不一致**，说明你设备上的音频资产与作者那台不同（作者自己承认这些文件会被 Apple 的 MobileAsset 静默更新替换过）——此时**绝对不能**直接写入 `silent-ios-format/` 那套静音件，必须按你设备的实际格式重新生成。

```sh
./静音件生成.sh <原件文件> [输出文件]      # 单个
./静音件生成.sh <原件所在目录>              # 批量
```

它读取原件的 **编码 / 采样率 / 声道 / 时长**，生成完全匹配的静音文件，并自动校验四项是否一致。

**⚠️ 这个工具要在 Mac 上跑**，不要拿到 Windows 去——它依赖 macOS 自带的 `afinfo` 和 `afconvert`。生成的静音件再拷到 Windows 使用。

### 🔴 关于"静音件怎么生成"的一个重要事实修正

作者的 README 说「两个静音文件都是用 ffmpeg 的 `anullsrc` 生成的」。**实测发现这对 CAF 那个不成立**：

```
[caf @ ...] muxing codec currently unsupported
Could not write header (incorrect codec parameters ?): Not yet implemented in FFmpeg
```

**ffmpeg 无法把 Opus 封装进 CAF**，而 iOS 27 真机的 `StopDisclosure.caf` 恰好是 Opus/CAF。所以 CAF/Opus 那条路必须用 macOS 的 `afconvert`，本工具的脚本就是这么分流处理的。

**验证状态（本机实测通过）**：用作者 dump 的两个真机原件跑过完整回归——

| 路径 | 结果 |
|---|---|
| CAF/Opus（走 `afconvert`） | 编码/采样率/声道全部一致，时长 **1.920000s 精确相同**（差 0.0000s） |
| AAC/m4a（走 `ffmpeg`） | 编码/采样率/声道全部一致，时长 1.617982s vs 原件 1.618639s（差 0.0007s） |
| 批量模式 | 处理 2 个，失败 0 个 |
| 错误路径 | 非音频文件、不存在文件、空目录均正确报错并返回退出码 1；无参数返回 2；临时目录无残留 |

> 顺带一个发现：**本工具生成的 m4a 比作者那套更精确**——作者的是 1.671837s（比原件长 53ms），本工具是 1.617982s（只差 0.7ms）。所以如果你走回退路线，用本工具生成的结果会比现成的好。当然，如果哈希匹配就直接用现成的，不必多此一举。

### 🔴 音频资源的格式陷阱（本项目最大的坑）

AirBeep 打包的静音件与 AirliftSilence **Windows 版自带的完全相同**（sha256 一致），但**两者都与真机原件不匹配**：

| 文件 | Windows 自带（❌ 不要用） | ✅ 推荐使用的（`silent-ios-format/`） | 真机原件 |
|---|---|---|---|
| `StartDisclosureWithTone.m4a` | AAC 44.1k **1.8340 s** | AAC 44.1k **1.6718 s** | AAC 44.1k 1.6186 s |
| `StopDisclosure.caf` | **PCM** 48k **1.7697 s** | **Opus** 48k **1.9400 s** | **Opus** 48k 1.9200 s |

**Stop 提示音的问题最大**：真机上是 **Opus**，Windows 版写的是 **PCM**，还短了 150 ms。

作者在自己的 iOS 仓库（`YiHoooong/AirliftSilence-iOS`）里配的那套才是按真机格式做的，已经取出放在 `silent-ios-format/`。

**因此：不要点 GUI 上那个「去除提示音」按钮**（它会写入 Windows 自带那套）。必须用命令行显式指定正确文件。

### 推荐静音件 SHA256

```
silent-StartDisclosureWithTone.m4a  5f989711c74b60ad054d822d1202f52ebac37065cff9f7939c868644b8eaf177
silent-StopDisclosure.caf           067b9b814203c67b5eed4855c353c044dee5d34081beaeab6e8224c6d850e950
```

### 作者 dump 的真机原件 SHA256（用于比对用户设备）

```
original-StartDisclosureWithTone.m4a  e4ff9f8a0cfa1994321492c509bcd166e5ef6d341e9caa2b41631ef64eca3b47
original-StopDisclosure.caf           6b9dd7f8a267a79b1ee2184e52d447c541f4bc76830424373a7bdf2fff9ef7be
```

---

## 六、操作流程（关键在「先读后写」）

详细步骤见 **`docs/AirliftSilence-Windows操作手册.md`**。核心顺序：

### 步骤 0：Windows 侧准备
1. 安装 **64 位 iTunes** 或 **Apple Mobile Device Support**（必须，漏洞依赖 `AirTrafficHost.dll`）
2. 把 `artifacts/airliftsilence/` 整个目录拷到 Windows（也可直接从 https://github.com/jiutinglifeng/airbeep-calltone-research 拉，exe 已提交在仓库里）
3. **双击运行 `预检.bat`** ← 🔴 **先做这一步**
   - 它会校验 9 个文件的哈希、检查驱动/Python/设备连接，有失败项会阻止你继续
   - ⚠️ 该脚本未在真实 Windows 上验证过，详见第五章的诚实声明；若它行为异常，改用手工 `certutil -hashfile <文件> SHA256` 逐个比对
4. ⚠️ exe 无签名，Windows Defender / SmartScreen 会拦；源码运行可绕开这一步

### 步骤 1：连接
数据线连 iPhone → **解锁** → 弹「信任此电脑」→ 点信任。
**「开发者模式」无需打开**（本方案不需要）。

### 步骤 2：先 dump 原件（🔴 关键设计）

> **在跑 read 之前，先做一次零风险的设备体检：**
> ```cmd
> python 设备体检.py scan
> ```
> 它只读 Media 目录，不触发 exploit。如果报告发现 `airlift-replaced-*` 或 `airlift-recovered-*`，**先按第四章把它抢救出来**，再继续——那可能是之前中断留下的原件。

```cmd
pip install pymobiledevice3
cd source-patched

python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf backup-StopDisclosure.caf --logging
python airlift.py read /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a backup-StartDisclosureWithTone.m4a --logging
```

> 🔴 **注意这里是 `cd source-patched`，不是 `cd src`。** `src/airlift.py` 原版有设备识别 bug，会让你误以为手机没连上——原因见第五章「必读」。静音文件和 `backup-*.caf` 会被写到 `source-patched/` 目录下。

**为什么先跑 `read`：**
- `read` 是**往返操作**（移到 Media → 读出 → 写回原位），成功时文件回到原样
- 所以它**同时完成了备份和管道验证**
- **万一 `read` 就失败，用户还没写任何东西**，损失最小

> 预期会打印 `⚠ 这个 iOS 版本没有在作者的测试列表里`——**这是正常的**。作者忘了把 `24A446` 加进代码白名单（`airlift.py:26` 的 `TESTED_BUILDS` 只有 `("27.0","24A435")` 和 `("27.0","24A5390f")`），但 README 明确写了 24A446 已验证。这只是警告，不阻止操作。

**dump 完立刻做两件事：**

**① 比对格式**（🔴 决定能否继续）：

```cmd
certutil -hashfile backup-StopDisclosure.caf SHA256
```

- **与 `original-StopDisclosure.caf` 哈希一致** → 用户设备音频与作者 dump 的完全相同，`silent-ios-format/` 可以直接用
- **不一致** → 🔴 **停下来**。说明该设备音频资产有差异（作者已承认这些文件会被 Apple 的 MobileAsset 静默更新替换过）。需要用 dump 出来的原件的**编码格式与时长**重新生成静音件，再继续

**② 把 dump 出来的原件复制到 U 盘 / 云盘**，不要只留在 Windows 上

### 步骤 3：替换

```cmd
python airlift.py replace /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf ..\silent-ios-format\silent-StopDisclosure.caf --backup device-backup-StopDisclosure.caf --logging

python airlift.py replace /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a ..\silent-ios-format\silent-StartDisclosureWithTone.m4a --backup device-backup-StartDisclosureWithTone.m4a --logging
```

每次约 2–4 分钟，全程保持解锁 + 连着数据线。

**🔴 每次替换后必须检查输出的 JSON：**

```json
{"ok": true, "replaced": "...", "size": 1399, "previousSize": 44325, "backup": "...\\device-backup-StopDisclosure.caf"}
```

| 输出 | 含义 | 动作 |
|---|---|---|
| `previousSize` 是数字，且 backup 文件存在 | ✅ 原件已成功读回并备份 | 继续 |
| `previousSize: null` / `backup: null` | 🔴 **原件没读回来**，留在设备 Media 目录（`airlift-replaced-<token>`） | **立刻停止**，按手册第四章情况 A 救回 |

### 步骤 4：实测
1. 打电话 → 开始录音 → 听是否还有提示音
2. 结束录音 → 听是否还有提示音
3. **重启手机，再测一次**（见第七章风险）

---

## 七、已知风险（必须向用户交代）

| 级别 | 风险 | 应对 |
|---|---|---|
| 🔴 | **「重启后依然有效」只有作者说过。** 作者在 README 称 27.0.1 上重启后有效，但有一条**第三方报告**（[AirliftSilence-iOS issue #3](https://github.com/YiHoooong/AirliftSilence-iOS/issues/3)，用户 karttv，iPhone 12 Pro / iOS 18.7.8）明确说：**"Windows 和 iOS 两个客户端都可成功替换。重启后，实际通话的提示音重新出现。"** | 重启后必须实测；失效就重跑一次 |
| 🟠 | **无第三方在 27.0.1 上复现。** 该仓库 **0 issue / 0 PR / Discussions 关闭**，`Verified on 27.0.1` 100% 是作者自述 | 步骤 2 的独立 dump 是唯一保险 |
| 🟠 | **随时可能被 Apple 修掉**（27.2 beta 3 已修） | 立刻关闭自动更新 |
| 🟠 | **音频资产可能被静默更新**（作者承认发生过一次） | 提示音自己回来了就重跑一遍 |
| 🟡 | **`replace` 是 fork 新增代码。** 上游只验证过 fresh-file writes，覆盖已有文件这条路径**无第三方复核** | 步骤 2 先用 `read` 验证管道 |
| 🟡 | **exe 无签名**，且 37 MB PyInstaller 产物无法逐行审计 | 改用源码运行（`src/*.py` 完全可读） |

**乐观面**：机制只是「移动文件 + 写文件」，不刷固件、不动系统分区，**无变砖机理**。最坏情况是目标路径缺一个提示音文件，可手工补回。

---

## 八、失败恢复预案

唯一失败模式：**原件被移到 Media 后没被写回**，表现为目标路径缺失文件。

### 第一步：用 `设备体检.py` 找到并抢救（✅ 首选，已测试）

```cmd
python 设备体检.py scan
```

它会列出 Media 里的所有 `airlift-*` 残留，标出哪些可能是原件、给出大小与 SHA256，**并直接打印出该执行的抢救命令**。然后：

```cmd
python 设备体检.py pull /var/mobile/Media/airlift-replaced-XXX rescued.bin
```

抢救后把打印出来的 SHA256 与我们已知的原件哈希（见附录）比对。**如果匹配，你就找回了唯一的一份原件，务必立刻复制到 U 盘。**

> 这个脚本是只读的，跑多少次都不会改动设备；对比下面那段手工命令也安全得多。

<details>
<summary>备用：不用脚本时的手工命令（等价，但更容易写错）</summary>

```cmd
python -c "import asyncio; from pymobiledevice3.lockdown import create_using_usbmux; from pymobiledevice3.services.afc import AfcService
async def m():
    ld = await create_using_usbmux()
    afc = AfcService(lockdown=ld)
    await afc.connect()
    d = await afc.get_file_contents('/var/mobile/Media/airlift-replaced-XXX')
    open('rescued.caf','wb').write(d)
    print(len(d))
asyncio.run(m())"
```

</details>

### 第二步：写回（此时目标路径是空的，用 `write` 正好适用）

```cmd
python airlift.py write /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf rescued.caf --logging
```

### 如果工具自带备份也丢了

用步骤 2 里复制到 U 盘的独立 dump，同样用 `write` 命令写回。

---

## 九、技术背景（供理解与排障）

### 漏洞机制

AirTraffic 是 Apple 从 Mac 同步媒体（含 Books）到 iOS 的官方通道。逃逸点：

1. 通过 `com.apple.streaming_zip_conduit` 上传特制 StreamingZip 包，内含**相对符号链接** `p0/p1/p2/link → ../../../<目标路径>`
2. 用 AFC 覆盖写 `Media/Books/Sync/Books.plist`，其 AssetID 带 `..` 路径
3. 跑完整 AirTraffic 状态机（`HostInfo → RequestingSync → ReadyForSync → FinishedSyncingMetadata → AssetManifest → FileComplete`）
4. **漏洞点在 `-[ATAirlock processCompletedAsset:]`**：
   - AssetID（identifier）**未做路径校验**，可用 `..` 逃出 `/var/mobile/Media/Airlock/Book`
   - destination **只做字符串前缀检查** `hasPrefix:@"/var/mobile/Media/"`，不解析符号链接后的真实路径
   - 最后用 `moveItemAtPath:`，第一次移动符号链接、第二次以它为跳板把内容写到 Media 之外

### 替换为什么是「先搬走再写」

AirTraffic 的 `moveItemAtPath:toPath:` **不允许覆盖已存在文件**。所以「替换」实际是：

```
第一步：把目标文件搬到 Media 的临时名 (airlift-replaced-<token>)  ← 原位空出来
第二步：把软链接搬到 Media
第三步：把 payload 写进 lnk/leaf                             ← 在空出的原位新建
```

**安全设计**：`_cleanup` 只在 `previous is not None` 时才删 Media 里的原件（`airlift.py:529-531`）——**宁可留副本也不毁原件**。

### 涉及的私有服务

```
主机侧（Windows）：AirTrafficHost.dll + CoreFoundation.dll（ctypes 调用）
iOS 侧：         com.apple.streaming_zip_conduit → com.apple.afc → com.apple.atc
                 → AirTrafficDevice → Books sync client → ATLegacyAssetLink → ATAirlock
```

### CLI 语法参考（`airlift.py`）

```
python airlift.py write   <ios_path> <local_file> [--device UDID] [--logging]
python airlift.py read    <ios_path> <output_file> [--device UDID] [--logging]
python airlift.py replace <ios_path> <local_file> [--backup <path>] [--device UDID] [--logging]
```

`--backup` **只在成功读回原件时才写文件**，所以必须看 JSON 里的 `previousSize`。

### Grappa 令牌

10 个预生成令牌，为 `(version=1, deviceType=0, protocolVersion=1)` 生成——正是 iOS 27 设备广播的参数。**不是每台设备一份**。来源：AirCard-iOS 的 `GrappaHelper.m`。

作者原话：「**27.0.1 并没有修掉这个漏洞 —— 它只是加了一道锁，而钥匙是通用的。**」

---

## 十、环境事实（便于判断工具可用性）

### 用户的 Mac（已检查）
| 项 | 状态 |
|---|---|
| 系统 | macOS 27.0.1 (26A434)，Apple M4 |
| Xcode | ❌ **未安装**（`xcode-select` 指向 Command Line Tools） |
| Rust 工具链 | ❌ 未安装 |
| 侧载工具 | ❌ 均未安装 |

### 用户的 Windows
- **Intel/AMD 架构**（已确认）→ AirliftSilence 可用
- 曾有会话误判为「只有 Mac」，后经用户澄清存在独立 Windows 电脑

### 用户的 Apple ID
- **只有免费 Apple ID**，明确不打算购买付费开发者账号
- （本方案不需要任何签名，此条已不构成约束）

### GitHub CLI（用户 Mac 上）
- `gh` v2.97.0，已认证为 **`jiutinglifeng`**，scope 含 `repo`、`workflow`

---

## 十一、仓库状态

- 工作区：`/Users/jiutinglifeng/Documents/claude-code-test/airbeep`
- 这是 **`LinkPass888/AirBeep` 的克隆**（作为研究素材），不是用户原创项目
- 本次研究会话新增的内容都在 `docs/` 和 `artifacts/` 下，与上游源码分开

### git remote 配置（⚠️ 别推错地方）

| remote | 指向 | 用途 |
|---|---|---|
| **`myrepo`** | `jiutinglifeng/airbeep-calltone-research` | ✅ **我们自己的仓库，要推就推这里** |
| `origin` | `LinkPass888/AirBeep` | ⛔ 上游别人的仓库，**只读参考，不要推** |
| `upstream` | `frs0n/placard` | ⛔ 更上游，只读参考 |

推送命令：`git push myrepo main`

### 我们的仓库

- 地址：**https://github.com/jiutinglifeng/airbeep-calltone-research**（public）
- 已推送的 HEAD：`f314992`
- 许可：GPL-3.0（继承自上游 AirBeep）
- 注意：仓库里那两个 64 MB 的 `libairlift_ffi.a` 来自上游源码，GitHub 会警告超过 50 MB 推荐值，但推送是成功的、不影响使用

### 已建立的会话目标

为了让跨会话不丢目标，已创建一个持久化 goal（id `goal-75687702-246e-4999-a988-8c1892e9e8c9`），其 objective 里固化了四条关键约束（不升级系统、先读后写、检查 previousSize、重启后复测）。

### 本次会话产出的文档

| 文件 | 内容 |
|---|---|
| `docs/HANDOFF.md` | **本文** |
| `docs/AirliftSilence-Windows操作手册.md` | 最终方案的操作手册 |
| **`docs/失败签名对照表.md`** | ✅ **出错时第一时间查这个**：把 `airlift.py` 的全部错误串映射到具体动作，分「目标是否已被动过」 |
| `docs/AirBeep-技术方案与实施文档.md` | AirBeep 方案分析（**已不是主路线**，保留作参考） |
| `docs/2026-10-11-核查补充.md` | GPT 对上述文档的核查与修正 |
| `docs/reference/` | 核查用原始证据（补丁全文、pin 版本源码、上游 README 等） |

---

## 十二、下次会话的待办清单

### 立即
- [ ] **确认用户已关闭 iPhone 自动更新**（最紧急，窗口在关闭）

### 执行
- [ ] 在 Windows 上装 64 位 iTunes / Apple Mobile Device Support
- [ ] 把 `artifacts/airliftsilence/` 拷到 Windows
- [ ] 连设备、信任
- [ ] **先跑 `read`** dump 两个原件
- [ ] **比对哈希**：`backup-*` vs `silent-ios-format/original-*`
  - [ ] 一致 → 继续
  - [ ] 不一致 → 🔴 停下，按设备实际格式重新生成静音件
- [ ] 把 dump 的原件复制到 U 盘
- [ ] 用 `replace` 写入 `silent-ios-format/` 那套静音件
- [ ] 检查每次的 JSON `previousSize` 不为 null
- [ ] 打电话实测

### 验证
- [ ] **重启手机后再测一次**（验证「重启失效」风险是否为真）
- [ ] 记录 Media 目录是否残留 `airlift-replaced-*`

### 未解决 / 待观察
- [ ] 用户设备上的 `StopDisclosure.caf` 究竟是 Opus 还是 PCM？**只有 dump 出来才知道**——这决定 `silent-ios-format/` 能否直接用
- [ ] 「重启后依然有效」在 24A446 上成立吗？（作者说成立，第三方在 18.7.8 上说不成立）
- [ ] 若 `silent-ios-format/` 也不匹配，需按实际格式用 ffmpeg 重新生成静音件（作者用的是 `anullsrc`）

---

## 十三、给下一个 AI 的提醒

1. **不要重新调研方案。** 路线已经选定并排除过 7 条替代路线，理由都在第四章。直接进入执行。
2. **不要用 GUI 的「去除提示音」按钮。** 它写入格式不匹配的静音件，具体见第五章。
3. **严格按「先读后写」顺序。** `read` 是先验证后动手的关键设计，不要跳过。
4. **盯住 JSON 的 `previousSize`。** 这是判断原件有没有安全备份的唯一信号。
5. **每一步的输出都要向用户索取并判断**，尤其第 2 步的 dump 结果和哈希比对——那决定能否进第 3 步。
6. **先提醒时间窗。** 见第二章：iOS 27.2 正式版预计 10 月 26 日那周发布，届时方案作废。这件事优先级高于所有技术步骤。
7. **出错时先查 `docs/失败签名对照表.md`。** 它把 `airlift.py` 的全部错误串按「目标是否已被动过」分类。关键认知：**`read` 和 `replace` 都不是只读操作**，两者都会先移动目标文件；`read` 失败会把目标留空，`replace` 失败会把目标留成静音版。原件在两种情况下都留在 Media，都能救。
8. **如果 dump 出来的原件与作者的 `original-*` 哈希不一致，不要硬写现成的静音件。** 回 Mac 上跑 `静音件生成.sh` 按实际格式生成。注意 `ffmpeg` 做不了 Opus/CAF，该脚本对 CAF 走的是 macOS 的 `afconvert`。
9. 用户偏好：**简洁直接、给默认判断让他否决、先确认再大改**。不要用长篇风险免责声明淹没技术内容；他明确表示法律风险不用讨论。
10. **先问用户走哪条路线**（见第零章）：macOS 更快、但 `ATHostConnection*` 未在 macOS 上验证过；Windows 是作者验证过的、但依赖未 pin 版本有 bug（已修）。**建议先试 macOS**——第一条 `read` 就能判断成败。

---

## 附录：全部文件 SHA256 速查

```
【主程序与源码】
AirliftSilence-v1.0.0.exe    3bb09e07d22660b9f98c3dd12cedd177af5802040d8c7aee52d89974e1de6e5e
src/airlift.py               d15d59a0d86b4a6c3d8606eb50798fe30f77dbd72c1bb5cf2de1e53e3d8bb6e0
src/airlift_gui.py           cadfc463a646c666db0816e5da306402d14fde4798d933cfe82fcd47cfb5e88f

【✅ 推荐使用的静音件】
silent-ios-format/silent-StartDisclosureWithTone.m4a  5f989711c74b60ad054d822d1202f52ebac37065cff9f7939c868644b8eaf177
silent-ios-format/silent-StopDisclosure.caf           067b9b814203c67b5eed4855c353c044dee5d34081beaeab6e8224c6d850e950

【作者 dump 的真机原件（用于比对用户设备）】
silent-ios-format/original-StartDisclosureWithTone.m4a  e4ff9f8a0cfa1994321492c509bcd166e5ef6d341e9caa2b41631ef64eca3b47
silent-ios-format/original-StopDisclosure.caf           6b9dd7f8a267a79b1ee2184e52d447c541f4bc76830424373a7bdf2fff9ef7be

【⚠️ Windows 版自带静音件（不要用）】
src/silent/StartDisclosureWithTone.m4a  efcde5b82b4ec6e9716e34622350dfed288142cbe4692d216141f347c8369580
src/silent/StopDisclosure.caf           c8ccb2c43e24cdd8ffb49bc33b6c523003158685d312cbb2c835d81ecbe8349e

【格式对照】
                        Windows 自带(❌)      推荐用(✅)        真机原件
Start .m4a              AAC 1.8340s          AAC 1.6718s       AAC 1.6186s
Stop  .caf              PCM 1.7697s          Opus 1.9400s      Opus 1.9200s

【目标文件】
/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a
/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf

【关键日期】
2026-10-23   iPhone Duo 发布（预装 iOS 27.1，不向其他机型推送）
2026-10-26   那周 —— iOS 27.2 正式版预计发布，漏洞作废的硬截止

【设备】
iPhone 18 Pro Max / iOS 27.0.1 (24A446)

【我们的仓库】
https://github.com/jiutinglifeng/airbeep-calltone-research
推送用 git push myrepo main
```


*本文写于 2026-10-11，与用户在 Mac 上的研究会话交接。*
*下一个会话在 Windows 上进行。*
