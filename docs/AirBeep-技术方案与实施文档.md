# AirBeep 技术方案分析与实施文档

> **后续核查（2026-10-11）**：请先读 [方案核查补充](2026-10-11-核查补充.md)。本文的「技术上可行」「LocalDevVPN 必需」「备份不会丢」等表述需要按补充文档收窄；目前没有目标 iPhone 的端到端实测。

> 文档目的：一是记录对 AirBeep 方案的完整技术分析与**已验证**的事实；二是列出**尚未验证、需要外部核实**的问题清单，供向 codex / GPT 求证。
>
> 文档内所有结论都标注了来源等级：
> - ✅ **已实证**：我们在本机通过命令、反编译、二进制符号检查、源码阅读直接确认
> - 📖 **上游文档**：来自上游仓库 README 或公开资料，未独立验证
> - ⚠️ **待验证**：尚未确认，列在第六章待求证

---

## 一、目标与结论摘要

**目标**：在 iPhone 18 Pro Max（iOS 27.0.1）上，消除系统通话录音的开始/结束提示音。

**结论**：方案在**技术上可行**，因为 iOS 27.0.1 恰好是该漏洞的**最佳支持版本**。但有两个硬性前提和一个硬性时间窗：

| 项 | 状态 |
|---|---|
| iOS 27.0.1 | ✅ 支持，且是上游主测试目标 |
| 需要 LocalDevVPN | ⚠️ 必要条件，国区已下架，需美区 Apple ID |
| 需要重签名安装 | ⚠️ 需要签名工具（免费 Apple ID 即可） |
| 时间窗 | 🔴 **一旦升级到 iOS 27.2 beta 3+，漏洞被 Apple 修补，永久失效** |

**最关键的决策：立刻关闭系统自动更新。**

---

## 二、已验证的事实（✅ 本机实证）

### 2.1 仓库状态

- 仓库 `LinkPass888/AirBeep` 已克隆至工作区根目录
- 当前 HEAD `e545efa` = tag `v2.4.0`（2026-10-10），工作区干净
- 97 个提交、5 个 tag（v2.0.0 → v2.4.0）
- 代码量：Swift / ObjC 合计约 **2400 行**
- 首提交内容是 "PosterBoard wallpaper manager"（换壁纸工具），说明项目从 `placard` 演化而来，非从零开发

### 2.2 项目分层

| 层 | 文件 | 职责 |
|---|---|---|
| UI | `airbeep/ContentView.swift`、`CallRecordingToneView.swift`、`AirBeepAboutView.swift` | 一个开关 + 状态卡 + 关于页 |
| 业务逻辑 | `airbeep/CallRecordingToneService.swift` | 状态机、备份、写后回读校验、失败回滚 |
| 配对与环境 | `airbeep/Airlift/PairingController.swift`、`Utilities.swift` | RPPairing 主机、Bonjour 广播、音频保活、本地网络权限探测 |
| FFI 桥 | `airbeep/Airlift/AirliftToneTransport.swift` | `dlsym` 取函数指针、actor 串行化阻塞调用 |
| 核心实现 | `Vendor/AirCard/AirliftFFI.xcframework`（Rust 静态库） | AirTraffic 沙箱逃逸：读文件、写目录 |

### 2.3 被修改的目标文件

硬编码在 `CallRecordingToneService.swift:94-109`：

```
/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a
/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf
```

替换为等长静音文件（`AirBeepStartSilence.m4a` / `AirBeepStopSilence.caf`，来自 AirliftSilence 项目）。

### 2.4 官方发布 IPA 的实测状态（✅ 已下载解包验证）

下载 `airbeep-v2.4.0-unsigned.ipa`（5.8 MB）并解包检查：

| 检查项 | 结果 |
|---|---|
| `MinimumOSVersion` | **26.0**（不是 README 说的 27.0） |
| 二进制架构 | arm64 单架构 ✅ 适配 A19 |
| 导出符号 `_al_exploit_read_file` / `_al_bytes_free` / `_al_set_target_host` | **全部存在** ✅ |
| 代码签名 | **完全没有签名**，无 `_CodeSignature`、无 `embedded.mobileprovision` |
| NetworkExtension / VPN 相关声明 | **无** ✅（这点很重要，说明重签名不需要特殊权限） |
| `UIBackgroundModes` | `audio` |
| `NSBonjourServices` | `_remotepairing-pairable-host._tcp`、`_aircardprobe._tcp` |
| `LSApplicationQueriesSchemes` | `localdevvpn`（用来唤起 LocalDevVPN） |

**结论：官方 IPA 可以直接下载使用，不需要编译。** 原因是 CI（`.github/workflows/release-unsigned.yml`）在构建前会先跑 `scripts/build-airlift-xcframework.sh` 重建 Rust 库，所以发布产物里的符号是完整的。

### 2.5 仓库内的静态库是过期版本（🔴 重要陷阱）

| 符号 | 仓库里的 `.a` | 官方 IPA 二进制 |
|---|---|---|
| `_al_exploit_read_file` | ❌ 缺失 | ✅ 存在 |
| `_al_bytes_free` | ❌ 缺失 | ✅ 存在 |
| `_al_set_target_host` | ❌ 缺失 | ✅ 存在 |

原因：CI 重建后的 xcframework **没有提交回仓库**，仓库里留的是 8 月的旧版本。

而 `airbeep.xcodeproj/project.pbxproj:304-306` 里有：

```
"-Wl,-u,_al_exploit_read_file",
"-Wl,-u,_al_bytes_free",
"-Wl,-u,_al_set_target_host",
```

`man ld` 对 `-u` 的原文：
> `-u symbol_name` — Specified that symbol symbol_name **must be defined for the link to succeed**.

**推论：新克隆仓库直接用 Xcode 构建会在链接阶段失败。** 必须先运行 `scripts/build-airlift-xcframework.sh`（需要 Rust 工具链 + Xcode 27）重建静态库。

**这同时也是"不要自己编译、直接用官方 IPA"这条路线的主要理由。**

### 2.6 本机环境现状（✅ 已检查）

| 项 | 状态 |
|---|---|
| macOS | 27.0.1（build 26A434），Apple M4 |
| Xcode | ❌ **未安装**（`xcode-select` 指向 Command Line Tools） |
| Rust 工具链 | ❌ 未安装 |
| 侧载工具 | ❌ 均未安装（无 ideviceinstaller / pymobiledevice3 / ios-deploy / Sideloadly） |

### 2.7 LocalDevVPN 的商店状态（✅ 通过 iTunes Lookup API 与 AppleCensorship 确认）

| 项 | 值 |
|---|---|
| 名称 | LocalDevVPN |
| 开发者 | Coxson Engineering LLC |
| 价格 | **免费** |
| 版本 | 1.3.0（2026-08-31 更新） |
| 最低系统 | iOS 14.0 |
| 分类 | Developer Tools |
| App Store ID | 6755608044 |
| 美区链接 | `https://apps.apple.com/us/app/localdevvpn/id6755608044` |
| **中国大陆区** | ❌ **2025-12-18 起下架**（175 个区中唯独国区不可用） |
| 评分 | 1.5★（较低，需注意） |

**注意**：它是免费 App，所以"用美区 Apple ID 下载"不需要绑卡、不需要付费。

---

## 三、技术原理

### 3.1 整体机制：AirTraffic 同步通道的路径穿越逃逸

AirBeep 自身**没有**突破沙盒的能力，真正的逃逸由 Rust 库 `AirliftFFI` 完成。机制来自上游项目 [airlift](https://github.com/0xjohnnydev/airlift)（作者 @0xjohnnydev），AirCard-iOS 将其移植为 Rust 实现。

攻击链（依据 `scripts/airlift-read-file.patch` 中的完整 Rust 源码 + 上游 README）：

1. **自配对**：App 在设备本地运行 RPPairing 主机（`PairingController.swift:169`），冒充 `Mac17,7` 的 Mac，通过 Bonjour 广播 `_remotepairing-pairable-host._tcp`，用音频后台保活（`UIBackgroundModes: audio`）维持进程存活，等用户在「设置 › 隐私与安全性 › 开发者模式」输入 PIN 完成配对。

2. **隧道**：配对产出的 plist 提供 RSD / AFC 通道；配合 **LocalDevVPN** 建立本地回环隧道，连到内网网关。Rust 侧默认候选地址列表（上游 `exploit.rs:246`）：
   ```
   ["10.7.0.1", "10.7.0.2", "10.7.0.3", "10.0.0.1", "172.16.0.1"]
   ```
   AirBeep 显式设置为首选 `10.7.0.1`（`AirliftToneTransport.swift:151`，通过 `al_set_target_host`）。

3. **借 AirTraffic 读书同步之名越权**：连接 `com.apple.streaming_zip_conduit` 上传一个特制 StreamingZip 包，内含**相对符号链接** `p0/p1/p2/link → ../../../<目标路径>`；再用 AFC 覆盖写 `Media/Books/Sync/Books.plist`，其 AssetID 里带 `..` 路径。

4. **触发系统自己搬文件**：连 `com.apple.atc` 跑完整 AirTraffic 状态机（`HostInfo → RequestingSync → ReadyForSync → FinishedSyncingMetadata → AssetManifest → FileComplete`）。为通过鉴权，会从 atc 的 `Capabilities` 消息抓 `GrappaSupportInfo`，再生成 "authentic Grappa token"。

5. **漏洞点**：`-[ATAirlock processCompletedAsset:]` 中
   - AssetID（identifier）**未做路径校验**，可用 `..` 逃出 `/var/mobile/Media/Airlock/Book`
   - destination **只做字符串前缀检查** `hasPrefix:@"/var/mobile/Media/"`，而不是解析符号链接后的真实路径
   - 最后用 `moveItemAtPath:`，第一次移动符号链接、第二次以它为跳板把内容写到 Media 之外

6. **读 vs 写**：
   - **写**：`al_exploit_write_dir` 直接批量写入目标目录（这只存在于 AirCard 上游）
   - **读**：上游 airlift 的机制是"把一个已知文件移进 Media → 经 AFC 读出 → 再移回"；AirBeep 通过**自己的补丁**新增了 `al_exploit_read_file` 来实现这条路

### 3.2 涉及的私有服务（✅ 上游 README 确认）

```
macOS 侧： MobileDevice.framework → AirTrafficHost.framework
iOS 侧：   com.apple.streaming_zip_conduit → com.apple.afc → com.apple.atc
           → AirTrafficDevice → Books sync client → ATLegacyAssetLink → ATAirlock → NSFileManager
```

### 3.3 官方支持矩阵（📖 上游 README）

| iOS 版本 | 状态 | 配对方式 |
|---|---|---|
| **iOS 27.0 – 27.0.1** | ✅ 支持 | 设备本地 Settings 配对 **或** 导入配对文件 |
| iOS 27.2 beta 1 – beta 2 | ✅ 支持 | 同上 |
| iOS 18.0 – 26.x | ✅ 支持 | **仅**导入配对文件（经 SideStore / LiveContainer / AltStore） |
| **iOS 27.2 beta 3+** | ❌ **已被 Apple 修补** | 无 |

> ⚠️ 上游 README 原文警告：**"Do not update past iOS 27.2 beta 2"**

### 3.4 AirBeep 工程实现中值得肯定的部分（✅ 源码阅读）

- **备份策略**：首次修改前必做备份，备份只写一次、永不覆盖（`CallRecordingToneService.swift:334`）
- **写后校验**：每次写入后强制回读并逐字节比对（`:374`）
- **失败回滚**：写失败自动尝试写回原内容（`:169`）
- **并发处理**：Rust 侧是阻塞 FFI，用 `actor` + 后台队列串行化（`AirliftToneTransport.swift:42`），不阻塞主线程
- **配对文件兼容性**：支持 `aircard_pairing.plist` / `airlift_pairing.plist` / 任意 plist，并自动规范化；也支持 `UIDocumentPicker` 手动导入
- **操作中屏幕常亮 + 红色警告横幅**（`:230`），避免用户中途退出导致半途状态

### 3.5 已知的实现缺陷（✅ 源码阅读）

1. **初始状态是假设而非事实**：`refresh()`（`:118`）在缓存为空时直接取 `.systemTone`。若用户此前静音过又重装 App（缓存丢失但系统文件仍是静音版），界面会错误显示"系统原音"。

2. **备份无真伪校验**：`ensureBackup`（`:334`）只判断备份能否读出数据，一旦写成功便永不覆盖。若首次备份时读到的不是原始文件，错误内容会被永久固化。

3. **v2.4.0 的状态显示可能不准**：为规避 iOS 27.0.1 上读取不稳定，现在打开 App **完全不碰文件**，开关显示的是 `UserDefaults` 缓存值，可能与实际不符。作者自己也承认，因此加了"改系统语言可强制恢复"的兜底说明。

4. **"读"操作也带写副作用**：补丁里的 `exploit_read_file` 会往 `target_dir` 写入一个探针文件，因此即使只是状态检查，也会往 `/var/mobile/Library/CallServices/Greetings/default` 写东西。

5. **供应链**：构建脚本会静默从第三方仓库 `mak5er/AirCard-iOS` clone 代码并编译进 App（`build-airlift-xcframework.sh:5-6`），固定了 commit 但无哈希锁定或审计。

6. **文档与实现不一致**：README 说支持 iOS 27.0–27.2 B2、需 Xcode 27；实际 `IPHONEOS_DEPLOYMENT_TARGET = 26.0`；`SystemCompatibility.swift:9` 的运行时判定却宽到 18.0–27.2。三处三个说法，只有 26.0 生效。

---

## 四、实施路径（推荐路线）

### 路线对比

| 路线 | 优点 | 缺点 |
|---|---|---|
| **A. 用官方 IPA + 重签名**（推荐） | 不用编译，无需 Rust/Xcode；官方 IPA 符号完整已验证 | 仍需签名工具；免费证书 7 天过期 |
| B. 从源码构建 | 完全可控 | 必须先重建 Rust 静态库（需 Rust + Xcode 27 + 网络）；耗时长 |

**推荐路线 A**，因为已实证官方 IPA 的符号完整，编译是纯粹的多余步骤。

### 路线 A 的步骤轮廓

**前置：立刻关闭系统自动更新**（设置 › 通用 › 软件更新 › 自动更新 → 全关）

1. **准备美区 Apple ID**（免费，不需绑卡）
   - 用途：下载国区已下架的 LocalDevVPN
   - 只需要一个能登录 App Store 的免费账号

2. **在手机上安装 LocalDevVPN**
   - 用美区 Apple ID 登录 App Store → 搜索 LocalDevVPN → 下载
   - 装完可以切回原 Apple ID（已下载的 App 不受影响）

3. **下载 AirBeep 官方 IPA**
   - 已验证可用：`https://github.com/LinkPass888/AirBeep/releases/download/v2.4.0/airbeep-v2.4.0-unsigned.ipa`

4. **用免费 Apple ID 重签名并安装 AirBeep**（🟡 具体工具与流程待确认，见第六章 Q3）

5. **配置 LocalDevVPN 回环**
   - 需按 AirBeep 期望的地址配置（默认首选 `10.7.0.1`）
   - 🟡 具体参数（设备 IP / 隧道 IP / 子网掩码）待确认，见 Q2

6. **在 AirBeep 内完成配对**（iOS 27.0.1 支持设备本地配对）
   - 打开 AirBeep → 配对页 → 开始配对 → 屏幕显示 6 位 PIN
   - 进「设置 › 隐私与安全性 › 开发者模式 › Pair with AirBeep」输入 PIN

7. **拨动开关**，完成静音

8. **验证**：实际录一通电话，确认提示音消失

### 风险与兜底

- **备份不会丢**：原音文件备份存在 App 的 Documents 目录（`AirBeepBackups`），且 App 声明了 `UIFileSharingEnabled`，可以通过「文件」App 直接取出另存一份。**建议实施前先手动抄一份备份出来。**
- **兜底恢复手段**：作者提供的最后手段是**更改系统语言**，可强制系统重新生成默认提示音。此说法来自 CHANGELOG，⚠️ 未独立验证（见 Q7）。
- **证书 7 天过期**：免费 Apple ID 签的 App 每 7 天需重签。AirBeep 本体过期不影响已改的系统文件（改动是持久的），所以过期后**不需要**立刻重签——只有在想再次开关切换时才需要。

---

## 五、法律与合规说明

> 记录用户明确表达的判断：在中国大陆，通话录音只要录音者本人也是通话参与方，即属合法；且国产手机的通话录音功能普遍不带此类提示音。本方案在此前提下使用。

---

## 六、交给外部协作者的简报

> 这一章是写给另一个 AI 协作者（GPT / codex）的。前面二、三、四章是我们的分析结论，这一章说明**我们的处境、已经堵死的路、以及希望你帮忙突破的方向**。
>
> 我们刻意没有把问题拆成一条条待答题目——你比我们更清楚该往哪挖。下面的"缺口"只是我们目前认知的边界，不是问题清单的上限。

### 6.1 我们在做什么、卡在哪

用户有一台 **iPhone 18 Pro Max，iOS 27.0.1**。目标：消除系统通话录音的开始/结束提示音。选定的方案是开源工具 **AirBeep**（`LinkPass888/AirBeep`），它通过 AirTraffic 同步通道的路径穿越漏洞改写这两个文件：

```
/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a
/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf
```

**目前完全卡在"如何把一个未签名的 IPA 装进手机"这一步。** 用户的环境约束：

- 只有**免费 Apple ID**，明确不打算买 ¥688/年的开发者账号
- 手上**没有任何签名/侧载工具**，从零开始
- Mac 是 **macOS 27.0.1 + Apple M4，只装了 Command Line Tools，没有 Xcode、没有 Rust**
- 手机上也**没装 LocalDevVPN**（方案的必要组件），而它在**中国大陆区 App Store 已于 2025-12-18 下架**（175 个区中唯独国区不可用），美区免费在架

### 6.2 我们已经验证过的事实（不用你重新查）

这些是我们本机实测或读源码确认的，可以直接采信，能省你不少功夫：

**官方 IPA 是完整的、可以直接用，不需要编译**
- 已下载 `airbeep-v2.4.0-unsigned.ipa` 并解包，SHA256 `395f16d770b70cd5f8bb67106f247d2cd40746b2b9e2d5fd204dac6618c1aa4f`
- 二进制为 arm64 单架构，导出符号 `_al_exploit_read_file`、`_al_bytes_free`、`_al_set_target_host`、`_ALGetGrappaToken` **全部存在**
- `MinimumOSVersion = 26.0`，支持 iOS 27.0.1
- **完全未签名**，无 `_CodeSignature`、无 `embedded.mobileprovision`
- **不含任何 NetworkExtension / VPN 声明**，说明重签名 AirBeep 本身不需要特殊权限

**但仓库里的静态库是过期的（这是个陷阱）**
- `Vendor/AirCard/AirliftFFI.xcframework` 里的 `.a` **缺少**上述三个符号，因为 CI 重建后的产物没有提交回仓库
- 而 `project.pbxproj:304-306` 有 `-Wl,-u,_al_exploit_read_file` 等三个强制符号标志（`man ld`：`-u` 表示该符号**必须**被定义才能链接成功）
- 结论：**新克隆仓库直接用 Xcode 构建会在链接阶段失败**，必须先跑 `scripts/build-airlift-xcframework.sh` 重建。这也是我们放弃自编译路线的直接原因

**上游兼容性矩阵（来自 mak5er/AirCard-iOS README）**

| iOS 版本 | 状态 | 配对方式 |
|---|---|---|
| iOS 27.0 – 27.0.1 | ✅ 支持 | 设备本地 Settings 配对 或 导入配对文件 |
| iOS 27.2 beta 1–2 | ✅ 支持 | 同上 |
| iOS 18.0 – 26.x | ✅ 支持 | **仅**导入配对文件 |
| **iOS 27.2 beta 3+** | ❌ **已被 Apple 修补** | 无 |

上游原文警告：**"Do not update past iOS 27.2 beta 2"**。用户的 27.0.1 恰好是最佳版本之一，但时间窗在关闭。

### 6.3 我们的认知缺口（按当前判断的阻塞程度排序）

**缺口一：把未签名 IPA 装进手机这条路，我们完全没有经验**

macOS 27 + 免费 Apple ID + 无 Xcode，这个组合下该用哪个工具、走什么流程，我们不确定。已知候选：Sideloadly、AltStore、SideStore、爱思助手、各类 `resign_ipa.sh` 脚本。我们担心两件事：一是免费 Apple ID 的限制（7 天有效期？最多 3 个 App？需要注册设备 UDID？）；二是 Sideloadly 首次签名要联网连 Apple 服务器，国内网络环境可能连不上。

**这一条是当前唯一真正的阻塞点，优先级远高于其它所有缺口。**

**缺口二：LocalDevVPN 拿不到，替代品可行性未知**

它是方案的必要条件——AirBeep 靠它提供本地回环隧道访问设备内部服务（首选 `10.7.0.1`，Rust 侧 fallback 列表为 `10.7.0.1 / 10.7.0.2 / 10.7.0.3 / 10.0.0.1 / 172.16.0.1`）。它免费、美区在架，理论上用免费美区 Apple ID 就能下，但评分只有 1.5★，我们不知道是不是有什么坑。

另外我们发现了两条替代线索，但没能力判断它们能否满足需求：

- `tom-snow/Sidestore-ClashMi` 项目提到用 **ClashMi** 替代 LocalDevVPN / StosVPN
- `jkcoxson/LocalDevVPN` 是个开源仓库

**如果存在一个不需要美区 Apple ID 的替代方案，对用户价值极大。**

**缺口三：iOS 27.0.1 上的实机行为全是未知**

- 「设置 › 隐私与安全性 › 开发者模式 › Pair with AirBeep」这个入口在 27.0.1 上是否真的存在？配对时 App 需要后台保活，用户要切到「设置」，这两者会不会冲突？
- 静音文件是否真的与原文件等长？iOS 对这两个文件是否有完整性/签名校验？
- 静音后是否**真的完全没有提示音**，还是系统有别的兜底机制（软件合成音、从别处读取）？

**缺口四：风险与恢复手段没验证过**

- CHANGELOG 声称"更改系统语言可强制恢复原始提示音"，我们没有验证这个说法的原理是否成立，也不知道还有没有别的恢复手段
- 如果写入过程中 App 崩溃，文件处于半损坏状态会有什么表现
- 27.2 正式版是否已经发布？（如果已经发布且用户误升级，方案即失效）Apple 有没有可能通过 Rapid Security Response 在不升级系统的情况下修补？
- 修改这两个文件会不会影响通话录音功能本身、FaceTime、或第三方 App 的录音？

### 6.4 我们特别希望你做的事

除了补上上面的缺口，有三件事我们更希望你能主动做：

**1. 请自行验证，不要只凭记忆作答。** 我们做了一个本地证据包放在 `docs/reference/`，你可以直接读：

| 文件 | 内容 |
|---|---|
| `airbeep.patch` | AirBeep 为读文件功能写的完整 Rust 补丁（含 `al_exploit_read_file` 全部实现） |
| `pinned_lib.rs` / `pinned_airlift.h` | AirCard-iOS pin 住版本（`40640c4`）的 FFI 定义，`al_set_target_host` 在 `pinned_lib.rs:397` |
| `pinned_README.md` | pin 版本的兼容性矩阵原文 |
| `upstream_README.md` | 上游 [0xjohnnydev/airlift](https://github.com/0xjohnnydev/airlift) 的 README，**唯一讲透了漏洞原理的公开文档**（ATAirlock 校验伪代码、可写目录清单、三个私有服务链路） |
| `aircardios.html` | AirCard 中文官网下载页存档 |

你也可以自行 clone 这两个仓库（都是公开的）：
- `https://github.com/mak5er/AirCard-iOS`（`AirliftFFI` 的来源）
- `https://github.com/0xjohnnydev/airlift`（漏洞研究源头）

**2. 请挑战我们的方案选择，而不是只帮我们执行它。** 按第一性原理看：在 iOS 27.0.1 上"消除通话录音提示音"这个需求，**AirBeep 这条 AirTraffic 逃逸路线是不是最优解？** 我们可能一开始就问错了问题。具体想知道：

- 有没有**更短的路径**？比如更低的签名门槛、更简单的文件写入方式
- 有没有越狱工具支持 iOS 27.0.1，能绕开整个逃逸方案？
- 有没有系统设置、描述文件、或别的层面的开关？
- 考虑到用户只有免费 Apple ID、不想花钱、且从零开始——**有没有一条我们完全没想到的路？**

如果你判断 AirBeep 确实是最优解，直接说；如果你认为有更好的路，请明确说清代价对比。

**3. 注意时效性。** 现在是 2026 年 10 月，这个漏洞的生命周期很短（27.2 beta 3 已修补）。如果你的信息落后于这个时间点，请以检索到的最新情况为准，并**明确指出哪些结论可能已经过时**。

### 6.5 关于回答方式

- 请明确区分「实际查证到的」和「推测的」，后者请标注为推测
- 查不到的直接说查不到，**不要为了给出答案而编造**
- 如果你发现我们上面的分析有错误，请直接指出——我们要的是正确答案，不是一致性
- 结论按**可执行性**排序，我们最终需要的是"用户在 Mac 前该按什么顺序做什么"

---

## 七、附录：关键文件索引

| 文件 | 说明 |
|---|---|
| `airbeep/CallRecordingToneService.swift` | 核心业务逻辑（状态机、备份、校验、回滚） |
| `airbeep/Airlift/AirliftToneTransport.swift` | FFI 桥，`dlsym` + actor 串行化 |
| `airbeep/Airlift/PairingController.swift` | RPPairing 主机与 Bonjour 广播 |
| `airbeep/Airlift/Utilities.swift` | 音频保活、本地网络权限探测 |
| `airbeep/SystemCompatibility.swift` | 版本判定（18.0–27.2） |
| `scripts/airlift-read-file.patch` | **关键**：包含读文件功能的完整 Rust 实现 |
| `scripts/build-airlift-xcframework.sh` | 重建静态库（本机不具备条件） |
| `scripts/verify-airlift.sh` | 符号完整性校验脚本 |
| `.github/workflows/release-unsigned.yml` | CI 构建与发布流程 |
| `airbeep.xcodeproj/project.pbxproj` | 构建配置（含 `-Wl,-u` 强制加载符号） |

**交给外部协作者时，请一并附上 `docs/reference/` 目录**（见 6.4 节的说明）——里面是核查用的原始证据，能让协作者自己验证而不是凭记忆作答。

## 八、附录：关键数据速查

```
目标文件：
  /var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a
  /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf

AirBeep 下载：
  https://github.com/LinkPass888/AirBeep/releases/download/v2.4.0/airbeep-v2.4.0-unsigned.ipa

AirBeep 本地副本（已下载并校验）：
  artifacts/airbeep-v2.4.0-unsigned.ipa
  大小    5.5 MB (5,806,194 字节)
  SHA256  395f16d770b70cd5f8bb67106f247d2cd40746b2b9e2d5fd204dac6618c1aa4f
  校验    zip 完整性通过；四个关键符号 (_al_exploit_read_file / _al_bytes_free /
          _al_set_target_host / _ALGetGrappaToken) 全部存在

LocalDevVPN 美区：
  https://apps.apple.com/us/app/localdevvpn/id6755608044

隧道候选地址（Rust fallback 列表）：
  10.7.0.1 / 10.7.0.2 / 10.7.0.3 / 10.0.0.1 / 172.16.0.1

官方 IPA 实测：
  MinimumOSVersion 26.0 / arm64 / 未签名 5.8MB / 符号完整

本机环境：
  macOS 27.0.1 (26A434) / Apple M4 / 无 Xcode / 无 Rust / 无侧载工具

目标设备：
  iPhone 18 Pro Max / iOS 27.0.1
```

---

*文档生成时间：2026-10-11*
*分析对象：LinkPass888/AirBeep @ e545efa (v2.4.0)*
