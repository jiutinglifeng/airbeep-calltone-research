# iPhone 19,7 / iOS 27.0.1 (24A446) 的真机原件

本目录是**从真实设备 dump 出来的通话录音提示音原件**，用作独立备份与格式参照。

## 为什么需要它

仓库上游（`YiHoooong/AirliftSilence-iOS`）自带一份作者 dump 的原件，但**与这台设备的不一致**：

| 文件 | 本目录（24A446 实测） | 上游作者 dump |
|---|---|---|
| `StopDisclosure.caf` | Opus 48k **1.520000 s** | Opus 48k 1.920000 s |
| `StartDisclosureWithTone.m4a` | AAC 44.1k **1.618639 s** | AAC 44.1k 1.618639 s |

**Stop 提示音相差 400 毫秒。** 如果直接使用上游配套的静音件（1.940000 s），
会比这台设备的原件长 420 毫秒。

**结论：静音件必须按设备实际时长生成，不能照搬。** 生成工具见上级目录的
`静音件生成.sh`；本次实际使用的静音件是 `macos-port/silent-Stop.caf`
（1.520000 s）与 `macos-port/silent-Start.m4a`（1.617982 s）。

## 文件说明

| 文件 | 来源 | 用途 |
|---|---|---|
| `backup-StopDisclosure.caf` | `airlift.py read` 首次 dump | 替换前的原始状态 |
| `backup-StartDisclosureWithTone.m4a` | 同上 | 同上 |
| `device-backup-Stop.caf` | `airlift.py replace --backup` 读回 | 与上面互为印证，哈希一致 |
| `device-backup-Start.m4a` | 同上 | 同上 |

## SHA256

```
backup-StopDisclosure.caf            8cf667b245d49339821257044cc2aecb6d2ab9e0f7222c51363a44e1e8558903
backup-StartDisclosureWithTone.m4a   e653deab1ae16a7f0f51aa1ab39458acd4d82800ca83ef4bd6a0c63c009e2161
device-backup-Stop.caf               8cf667b245d49339821257044cc2aecb6d2ab9e0f7222c51363a44e1e8558903
device-backup-Start.m4a              e653deab1ae16a7f0f51aa1ab39458acd4d82800ca83ef4bd6a0c63c009e2161
```

## 怎么用

在设备上恢复原始提示音：

```sh
cd ../macos-port
AIRLIFT_PAIRING_CACHE=/tmp/pd3-pairing python airlift.py write \
  /var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf \
  ../设备原件备份-24A446/backup-StopDisclosure.caf --logging
```

（`write` 适用于目标路径为空的情况；若目标存在，用 `replace`。）
