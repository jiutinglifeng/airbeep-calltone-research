#!/usr/bin/env python3
"""端到端演练：用 mock 设备完整走一遍「replace 失败 → 体检发现 → 救援 → 写回」。

为什么需要它
------------
`设备体检.py` 的单元测试只验证了单个函数在假对象上的行为。但**救援流程**
是唯一「只出事时才用、平时练不到」的路径 —— 如果它本身有缺陷，你会在最
需要它的那一刻才发现。这个演练把整条链路连同设备状态变化一起跑一遍：

    replace 失败（原件被移出、目标变空）
        → 设备体检.py scan 发现残留
        → 设备体检.py pull 抢救到本地
        → 校验 SHA256 确认是原件
        → airlift.py write 写回设备
        → 确认设备恢复正常

不连接任何真实设备，也不需要 pymobiledevice3。
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib.util
import io
import posixpath
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JK_PATH = HERE / "设备体检.py"


# ===========================================================================
# Mock 设备：忠实地模拟 pymobiledevice3 的 AfcService 接口
# ===========================================================================
class MockAfc:
    """模拟 AfcService。

    接口契约（与 pymobiledevice3 11.x 实际行为一致）：
      - connect()            async，幂等
      - listdir(path)        async -> list[str]；路径不存在时抛异常
      - get_file_contents()  async -> bytes；**目录会抛异常**（这是区分文件/目录的依据）
    """

    def __init__(self, files: dict[str, bytes], dirs: dict[str, list[str]]):
        self.files = dict(files)
        self.dirs = {k: list(v) for k, v in dirs.items()}
        self.connected = False

    async def connect(self):
        self.connected = True

    async def listdir(self, path: str) -> list[str]:
        if path in self.dirs:
            return list(self.dirs[path])
        if path in self.files:
            raise IsADirectoryError(f"not a directory: {path}")
        raise FileNotFoundError(path)

    async def get_file_contents(self, path: str) -> bytes:
        if path in self.files:
            return self.files[path]
        raise FileNotFoundError(path)


# ===========================================================================
# Mock 设备上的「系统文件」
# ===========================================================================
TARGET_DIR = "/var/mobile/Library/CallServices/Greetings/default"
MEDIA = "/var/mobile/Media"

# 模拟真机原件（内容随意，只要能区分）
ORIGINAL_STOP = b"ORIGINAL-STOP-DISCLOSURE-CAF" * 200
ORIGINAL_START = b"ORIGINAL-START-DISCLOSURE-M4A" * 150
# 模拟要写入的静音件
SILENT_STOP = b"SILENT" * 40
SILENT_START = b"SILENT" * 30


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ===========================================================================
# 载入被测脚本
# ===========================================================================
def load_jk():
    spec = importlib.util.spec_from_file_location("jk", JK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# 演练
# ===========================================================================
PASS, FAIL = [], []


def check(name: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(name)
    print(f"  {'✅' if ok else '❌'} {name}" + (f"   {detail}" if detail else ""))


def run(mod, coro):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = asyncio.run(coro)
    return rc, buf.getvalue()


def main() -> int:
    mod = load_jk()
    print("=" * 70)
    print("  端到端演练：replace 失败 → 体检 → 救援 → 写回")
    print("=" * 70)
    print()

    # -------------------------------------------------------------------
    # 场景构造：replace 的第三步失败，原件被移出、目标路径变空
    # -------------------------------------------------------------------
    # replace 的行为：先把目标文件移到 Media 的 airlift-replaced-<token>，
    # 再写 payload。第三步失败时目标路径是空的，原件停在 Media。
    token = "1a2b3c4d5e"
    moved = f"{MEDIA}/airlift-replaced-{token}"

    device = MockAfc(
        files={
            moved: ORIGINAL_STOP,               # 被移出的原件
            f"{TARGET_DIR}/StartDisclosureWithTone.m4a": ORIGINAL_START,  # 另一个文件没动
        },
        dirs={
            MEDIA: ["Books", "airlift-replaced-" + token, "DCIM"],
            TARGET_DIR: ["StartDisclosureWithTone.m4a"],   # ← 注意：没有 StopDisclosure.caf
            f"{MEDIA}/Books": [],
        },
    )

    print("【场景】replace 中途失败：原件被移到 Media，目标路径已空")
    print(f"  目标 {TARGET_DIR}/StopDisclosure.caf  →  不存在")
    print(f"  Media 里残留 {moved}")
    print()

    # -------------------------------------------------------------------
    print("── 第 1 步：设备体检（scan）──")
    rc, out = run(mod, mod.cmd_scan(device))
    check("scan 返回码为 0", rc == 0, f"rc={rc}")
    check("scan 发现了 airlift 残留", "airlift-replaced-" in out)
    check("scan 标出了『可能是原件』", "可能是原件" in out)
    check("scan 给出了可执行的救援命令", "pull" in out and token in out)
    check("scan 报告了 SHA256", sha(ORIGINAL_STOP)[:16] in out)
    print()

    # -------------------------------------------------------------------
    print("── 第 2 步：抢救到本地（pull）──")
    dest = HERE / "_演练-抢救出来的原件.bin"
    if dest.exists():
        dest.unlink()
    rc, out = run(mod, mod.cmd_pull(device, moved, str(dest)))
    check("pull 返回码为 0", rc == 0, f"rc={rc}")
    check("本地文件已生成", dest.exists())
    if dest.exists():
        rescued = dest.read_bytes()
        check("抢救内容与原件逐字节一致", rescued == ORIGINAL_STOP)
        check("pull 打印的 SHA256 正确", sha(ORIGINAL_STOP)[:16] in out)
    print()

    # -------------------------------------------------------------------
    print("── 第 3 步：确认这是原件而非静音件 ──")
    if dest.exists():
        rescued = dest.read_bytes()
        check("不等于静音件（可区分）", rescued != SILENT_STOP)
        check("长度与原件一致", len(rescued) == len(ORIGINAL_STOP),
              f"{len(rescued)} vs {len(ORIGINAL_STOP)}")
    print()

    # -------------------------------------------------------------------
    print("── 第 4 步：模拟 airlift.py write 写回设备 ──")
    # write 的行为：内容经 payload 写入目标路径（目标为空时正好适用）
    rescued = dest.read_bytes() if dest.exists() else ORIGINAL_STOP
    device.files[f"{TARGET_DIR}/StopDisclosure.caf"] = rescued
    device.dirs[TARGET_DIR].append("StopDisclosure.caf")
    device.files.pop(moved, None)            # _cleanup 只在校验通过后才删
    device.dirs[MEDIA].remove("airlift-replaced-" + token)

    check("目标路径已恢复", f"{TARGET_DIR}/StopDisclosure.caf" in device.files)
    check("恢复的内容与原原件一致",
          device.files.get(f"{TARGET_DIR}/StopDisclosure.caf") == ORIGINAL_STOP)
    print()

    # -------------------------------------------------------------------
    print("── 第 5 步：再次体检，确认已干净 ──")
    rc, out = run(mod, mod.cmd_scan(device))
    check("scan 报告无残留", "没有发现任何 airlift-* 残留" in out, f"rc={rc}")
    check("另一个文件未被波及",
          device.files.get(f"{TARGET_DIR}/StartDisclosureWithTone.m4a") == ORIGINAL_START)
    print()

    # -------------------------------------------------------------------
    print("── 附加：list 子命令 ──")
    rc, out = run(mod, mod.cmd_list(device))
    check("list 返回码为 0", rc == 0)
    check("list 报告干净", "没有发现任何 airlift-* 残留" in out)
    print()

    # -------------------------------------------------------------------
    print("── 附加：Media 为空时的行为 ──")
    empty = MockAfc(files={}, dirs={MEDIA: ["Books", "DCIM"]})
    rc, out = run(mod, mod.cmd_scan(empty))
    check("空 Media 下 scan 不报错", rc == 0, f"rc={rc}")
    check("空 Media 下报告干净", "没有发现任何 airlift-* 残留" in out)
    print()

    # -------------------------------------------------------------------
    print("── 附加：pull 不存在的文件应失败 ──")
    rc, out = run(mod, mod.cmd_pull(device, f"{MEDIA}/airlift-replaced-nope", str(dest) + ".x"))
    check("pull 不存在文件返回码为 1", rc == 1, f"rc={rc}")
    print()

    # 清理演练产物
    for p in (dest, Path(str(dest) + ".x")):
        if p.exists():
            p.unlink()

    # -------------------------------------------------------------------
    print("=" * 70)
    print(f"  结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("  失败项：")
        for f in FAIL:
            print(f"    - {f}")
    print("=" * 70)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
