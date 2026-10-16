#!/usr/bin/env python3
"""设备体检 / 原件救援工具（只读，全程不触发 exploit）

用途
----
本脚本只用普通 AFC 读取设备的 /var/mobile/Media 目录，不调用任何
AirTraffic 逃逸逻辑，因此**不会移动、修改或删除设备上的任何文件**。

它解决两个问题：

1. **写操作前**：确认 Media 里有没有「孤儿副本」——即之前某次失败的
   操作把原件移走却没写回，留下的 airlift-replaced-* / airlift-recovered-*
   / airlift-src-* / airlift-link-* 文件。这些文件对普通文件管理器不可见，
   但它们是真实存在的、可能是唯一的原件。

2. **写操作失败后**：把抢救出来的原件字节保存到本地，供 restore 使用。

为什么只读 Media 就够了
----------------------
两个提示音文件的真实路径在 /var/mobile/Library/CallServices/...，普通
AFC 读不到。但 AirTraffic 逃逸的失败模式恰好是「把文件搬到 Media 后没
写回」——所以 Media 才是需要检查的地方，而 Media 是 AFC 的管辖范围。

用法
----
    python 设备体检.py list        # 列出 Media 根目录下所有残留文件
    python 设备体检.py scan        # 递归扫描并识别 airlift-* 残留，报告大小与哈希
    python 设备体检.py pull <路径> <保存到本地>   # 把某个 Media 文件拉回本地

示例
----
    python 设备体检.py scan
    python 设备体检.py pull /var/mobile/Media/airlift-replaced-1a2b3c4d5e rescued.caf

注意
----
- 需要 pip install pymobiledevice3
- 需要 iPhone 用数据线连接、解锁、并已「信任此电脑」
- 本脚本是只读的：不含任何写入、移动、删除操作
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import posixpath
import sys
from pathlib import Path
from typing import Iterable

# pymobiledevice3 的 import 延后到真正连设备时再做。
# 原因：模块级 import 会让本文件无法在没装依赖的环境下被导入 —— 既不利于
# 单元测试/演练（本仓库的 演练-救援流程.py 就需要导入它但不需要真依赖），
# 也让「缺依赖」这个错误在 import 阶段就抛出、掩盖了真正的用法说明。
_create_using_usbmux = None
_AfcService = None


def _ensure_deps():
    """按需加载 pymobiledevice3。只在真正要连设备时调用。"""
    global _create_using_usbmux, _AfcService
    if _create_using_usbmux is not None:
        return
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.afc import AfcService
    except ImportError:
        print("缺少依赖，请先运行：  pip install pymobiledevice3", file=sys.stderr)
        raise SystemExit(2)
    _create_using_usbmux = create_using_usbmux
    _AfcService = AfcService


MEDIA_ROOT = "/var/mobile/Media"

# 这些前缀是 airlift 系工具在 Media 里留下的临时对象。
# replaced / recovered 里可能是原件，优先级最高。
PREFIXES = (
    "airlift-replaced-",   # replace 失败时被移出的原件
    "airlift-recovered-",  # read 恢复出来的副本
    "airlift-src-",        # 上传的 staging 目录
    "airlift-link-",       # 搬到 Media 的符号链接
)


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _device_info(lockdown) -> tuple[str, str, str, str]:
    """读取设备信息，返回 (产品型号, 系统版本, 构建号, 设备名)。

    刻意写成对 pymobiledevice3 版本变化不敏感的形式：
    该库迭代极快（PyPI 上已有 700+ 个版本），属性名会随重构变动。
    例如 `product_version` / `product_build_version` 是 property，
    而 `product_type` 在 lockdown 客户端上**并不存在**（它只属于 irecv
    子系统），照抄就会抛 AttributeError。所以每个字段都按
    「属性优先 → all_values → get_value」三级兜底。
    """
    # ---- 产品型号 ----
    pt = getattr(lockdown, "product_type", None)
    if not pt:
        try:
            pt = (getattr(lockdown, "all_values", None) or {}).get("ProductType")
        except Exception:
            pt = None
    if not pt:
        try:
            pt = await lockdown.get_value(key="ProductType")
        except Exception:
            pt = None

    # ---- 系统版本 ----
    ver = getattr(lockdown, "product_version", None)
    if not ver:
        try:
            ver = await lockdown.get_value(key="ProductVersion")
        except Exception:
            ver = None

    # ---- 构建号 ----
    bld = getattr(lockdown, "product_build_version", None)
    if not bld:
        try:
            bld = await lockdown.get_value(key="BuildVersion")
        except Exception:
            bld = None

    # ---- 设备名 ----
    try:
        nm = await lockdown.get_value(key="DeviceName")
    except Exception:
        nm = None

    pt = pt or "unknown"
    return (str(pt), str(ver or "unknown"), str(bld or "unknown"), str(nm or pt))


async def _connect():
    # 先确认依赖，再打印动作。否则缺依赖时会先输出「正在查找…」再报错，
    # 看起来像是真的去找过设备了。
    _ensure_deps()
    print("正在查找已连接的 iPhone …")

    # 配对记录缓存目录：默认在 $HOME/.pymobiledevice3。若该路径不可写
    # （受限环境、只读 HOME、容器等），pymobiledevice3 会抛
    # PermissionError: Operation not permitted，看起来像设备问题其实是
    # 写权限问题。可用 AIRLIFT_PAIRING_CACHE 覆盖。
    kwargs = {}
    cache = os.environ.get("AIRLIFT_PAIRING_CACHE")
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        kwargs["pairing_records_cache_folder"] = Path(cache)
        print(f"  配对记录缓存: {cache}")

    try:
        lockdown = await _create_using_usbmux(**kwargs)
    except PermissionError as exc:
        print(f"✗ 无法建立连接：{exc}", file=sys.stderr)
        print("   这通常是 pymobiledevice3 不能写配对记录缓存目录导致的，"
              "与设备无关。", file=sys.stderr)
        print("   试试：  AIRLIFT_PAIRING_CACHE=/tmp/pd3-pairing python 设备体检.py scan",
              file=sys.stderr)
        raise SystemExit(1)

    afc = _AfcService(lockdown=lockdown)
    await afc.connect()

    pt, ver, bld, name = await _device_info(lockdown)
    print(f"✓ 已连接：{name} · {pt} · iOS {ver} ({bld})")

    if (ver, bld) == ("27.0.1", "24A446"):
        print("  ✅ 系统版本与已验证环境完全一致")
    else:
        print(f"  ⚠ 该系统版本未在作者验证范围内（作者验证的是 27.0.1 / 24A446），仅作参考")

    if "iPhone" not in pt and pt != "unknown":
        print(f"  ⚠ 产品型号 '{pt}' 看起来不是 iPhone，请确认连的是目标设备")
    print()
    return afc


async def _listdir(afc: "AfcService", path: str) -> list[str]:
    try:
        return await afc.listdir(path)
    except Exception:
        return []


async def cmd_list(afc: "AfcService") -> int:
    print(f"== {MEDIA_ROOT} 根目录 ==")
    entries = await _listdir(afc, MEDIA_ROOT)
    if not entries:
        print("  （空，或无法读取）")
        return 0

    found = False
    for name in sorted(entries):
        if name in (".", ".."):
            continue
        flagged = any(name.startswith(p) for p in PREFIXES)
        if flagged:
            found = True
            print(f"  🔴 {name}   ← airlift 残留")

    if not found:
        print("  ✅ 没有发现任何 airlift-* 残留")
        print("     说明之前没有操作在「移出后没写回」的状态下中断过。")
    else:
        print()
        print("  ⚠ 发现残留。请立即用 scan 查看详情，并把可能是原件的文件 pull 下来。")
    return 0


async def _probe(afc: "AfcService", abspath: str) -> tuple[str, int, str]:
    """判断路径是文件还是目录，并取回详情。

    不依赖 stat() 的字段名——直接用「能不能读出内容」来区分：
    AFC 的 get_file_contents 对目录会抛错，对文件返回 bytes。
    这样只需要 listdir 与 get_file_contents 两个 API，而它们的语义
    已被 airlift.py 自身的用法证实。
    """
    try:
        data = await afc.get_file_contents(abspath)
        return ("file", len(data), f"文件  sha256={sha256(data)}")
    except Exception:
        pass

    # 读不出内容，尝试当目录列一层
    inner = await _listdir(afc, abspath)
    if inner:
        detail = f"目录，含 {len(inner)} 项"
        for item in sorted(inner)[:6]:
            detail += f"\n        └ {item}"
        if len(inner) > 6:
            detail += f"\n        └ …还有 {len(inner) - 6} 项"
        return ("dir", 0, detail)

    return ("unknown", 0, "无法读取（既不是可读文件，也不是可列目录）")


async def cmd_scan(afc: "AfcService") -> int:
    print("== 扫描残留 ==")
    print()

    roots: list[tuple[str, str]] = []
    for name in sorted(await _listdir(afc, MEDIA_ROOT)):
        if name in (".", ".."):
            continue
        if any(name.startswith(p) for p in PREFIXES):
            roots.append((name, posixpath.join(MEDIA_ROOT, name)))

    hits: list[tuple[str, str, int, str, str]] = []
    for label, abspath in roots:
        kind, size, detail = await _probe(afc, abspath)
        hits.append((label, abspath, size, kind, detail))

    if not hits:
        print("  ✅ 没有发现任何 airlift-* 残留。")
        print("     说明之前没有操作在「移出后没写回」的状态下中断过。")
        return 0

    print(f"  发现 {len(hits)} 个残留对象：")
    print()
    for label, abspath, size, ftype, detail in hits:
        is_original = label.startswith(("airlift-replaced-", "airlift-recovered-"))
        kind = "★ 可能是原件" if is_original else "临时对象"
        print(f"  🔴 {label}")
        print(f"     路径   {abspath}")
        if ftype == "file":
            print(f"     大小   {human(size)}  ({size} 字节)")
        print(f"     类别   {kind}")
        print(f"     {detail}")
        print()

    print("─" * 60)
    print("下一步：")
    print("  如果上面有 airlift-replaced-* 或 airlift-recovered-*，它很可能是")
    print("  唯一的原件。用下面的命令把它抢救到本地：")
    print()
    for label, abspath, _, _, _ in hits:
        if label.startswith(("airlift-replaced-", "airlift-recovered-")):
            print(f"    python 设备体检.py pull {abspath} rescued-{label}.bin")
    print()
    print("  抢救出来后，如果目标提示音文件在设备上已不存在，用 write 写回：")
    print("    python airlift.py write /var/mobile/Library/CallServices/Greetings/default/<文件名> rescued-<文件名>.bin --logging")
    return 0


async def cmd_pull(afc: "AfcService", remote: str, local: str) -> int:
    if not remote.startswith("/"):
        remote = posixpath.join(MEDIA_ROOT, remote)
    print(f"正在读取 {remote} …")
    try:
        data = await afc.get_file_contents(remote)
    except Exception as exc:
        print(f"✗ 读取失败：{exc}", file=sys.stderr)
        return 1

    with open(local, "wb") as fh:
        fh.write(data)

    print(f"✓ 已保存到 {local}")
    print(f"  大小   {human(len(data))}  ({len(data)} 字节)")
    print(f"  sha256 {sha256(data)}")
    print()
    print("请把上面的 sha256 与已知的原件哈希比对：")
    print("  original-StartDisclosureWithTone.m4a  e4ff9f8a0cfa1994321492c509bcd166e5ef6d341e9caa2b41631ef64eca3b47")
    print("  original-StopDisclosure.caf           6b9dd7f8a267a79b1ee2184e52d447c541f4bc76830424373a7bdf2fff9ef7be")
    return 0


USAGE = """\
设备体检 / 原件救援工具（只读，不触发 exploit）

用法：
    python 设备体检.py list                         列出 Media 根目录的 airlift 残留
    python 设备体检.py scan                         扫描残留并报告大小与哈希
    python 设备体检.py pull <Media路径> <本地文件>   把残留文件抢救到本地

说明：
    本脚本只用普通 AFC 读 /var/mobile/Media，不会修改设备上任何文件。
    写操作之前先跑一次 scan 是好习惯。
"""


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0

    cmd = args[0]

    async def run() -> int:
        afc = await _connect()
        if cmd == "list":
            return await cmd_list(afc)
        if cmd == "scan":
            return await cmd_scan(afc)
        if cmd == "pull":
            if len(args) != 3:
                print("用法：python 设备体检.py pull <Media路径> <本地文件>", file=sys.stderr)
                return 2
            return await cmd_pull(afc, args[1], args[2])
        print(USAGE)
        return 2

    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        print("\n已取消。")
        return 130
    except Exception as exc:
        print(f"\n✗ 出错：{exc}", file=sys.stderr)
        print("\n如果报 'no USB devices found'，请检查：")
        print("  1. 数据线是否支持数据传输（部分线只能充电）")
        print("  2. iPhone 是否已解锁")
        print("  3. 是否点了「信任此电脑」")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
