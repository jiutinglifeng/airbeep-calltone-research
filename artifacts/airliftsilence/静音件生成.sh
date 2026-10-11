#!/bin/bash
#
# 静音件生成器 —— 按设备原件的实际格式，生成时长与编码完全匹配的静音文件
#
# 什么时候需要它
# --------------
# 操作手册步骤 3 要求把设备原件 dump 下来、与作者 dump 的 original-* 比对
# SHA256。**如果哈希不一致**，说明你设备上的音频资产与作者那台不同（作者
# 自己承认这些文件会被 Apple 的 MobileAsset 静默更新替换过）。此时绝对不
# 能直接写入 silent-ios-format/ 那套静音件，必须按你设备的实际格式重新生成。
#
# 本脚本就是做这件事的。
#
# 为什么不是所有格式都能用 ffmpeg 生成
# ------------------------------------
# 实测发现：**ffmpeg 不支持把 Opus 封装进 CAF**（libopus @ caf 报
# "muxing codec currently unsupported"）。而 iOS 27 时代真机的
# StopDisclosure.caf 恰好是 Opus/CAF。所以 CAF/Opus 走 macOS 自带的
# afconvert，其余格式走 ffmpeg。
#
# 用法
# ----
#     ./静音件生成.sh <原件文件> [输出文件]
#     ./静音件生成.sh <原件所在目录>        # 批量处理目录下所有音频
#
# 示例
# ----
#     ./静音件生成.sh backup-StopDisclosure.caf my-silent-Stop.caf
#     ./静音件生成.sh ./dumped/
#
# 依赖（macOS 自带，无需安装）
# --------------------------
#     afinfo    读格式     /usr/bin/afinfo
#     afconvert 生成 Opus/CAF
#     ffmpeg    生成其余格式（需要自行安装，如 brew install ffmpeg）
#
set -euo pipefail

RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; BLD=$'\033[1m'; RST=$'\033[0m'

# 临时目录登记表。必须在此处初始化：脚本用了 set -u，而 EXIT trap 在
# 任何退出路径上都会跑，若变量未定义会二次报错。
CLEANUP_DIRS=""
cleanup() {
  local d
  for d in $CLEANUP_DIRS; do
    [ -n "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

die() { echo "${RED}✗ $*${RST}" >&2; exit 1; }
info() { echo "  $*"; }
ok() { echo "  ${GRN}✓${RST} $*"; }
warn() { echo "  ${YEL}!${RST} $*"; }

command -v afinfo >/dev/null 2>&1 || die "找不到 afinfo（本脚本需要 macOS）"

ffmpeg_bin=""
if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg_bin="$(command -v ffmpeg)"
fi

# ---------------------------------------------------------------------------
# 读取音频文件的格式信息
#
# 结果写入全局变量 PROBE_RATE / PROBE_CH / PROBE_CODEC / PROBE_DUR。
#
# ⚠️ 注意：**不要**在 $(...) 命令替换里调用探测逻辑。命令替换会开子 shell，
# 其中的 die/exit 只结束子 shell，外层脚本会拿着空值继续跑下去，产生
# 「请手工生成一个 Hz / ch / s 的文件」这种空值报错。所以这里用全局变量。
# ---------------------------------------------------------------------------
PROBE_RATE=""; PROBE_CH=""; PROBE_CODEC=""; PROBE_DUR=""

probe() {
  local f="$1"
  local line

  # afinfo 对非音频文件会非零退出。必须显式判断，否则后续 grep 会掩盖失败。
  if ! afinfo "$f" >/dev/null 2>&1; then
    die "不是受支持的音频文件（afinfo 无法解析）：$f"
  fi

  line="$(afinfo "$f" 2>/dev/null | grep -m1 '^Data format:')" || true
  [ -n "$line" ] || die "读不到音频格式信息：$f"

  # 形如: Data format:     1 ch,  48000 Hz, opus (0x00000000) ...
  PROBE_CH="$(echo "$line"    | sed -n 's/.*Data format:[[:space:]]*\([0-9]*\) ch.*/\1/p')"
  PROBE_RATE="$(echo "$line"  | sed -n 's/.*,[[:space:]]*\([0-9]*\) Hz.*/\1/p')"
  PROBE_CODEC="$(echo "$line" | sed -n 's/.*[0-9] Hz,[[:space:]]*\([A-Za-z0-9_]*\).*/\1/p')"
  PROBE_DUR="$(afinfo "$f" 2>/dev/null | sed -n 's/^estimated duration:[[:space:]]*\([0-9.]*\).*/\1/p' | head -1)"

  [ -n "$PROBE_CH" ] && [ -n "$PROBE_RATE" ] && [ -n "$PROBE_CODEC" ] \
    || die "解析音频格式失败：$line"
  [ -n "$PROBE_DUR" ] || PROBE_DUR="0"

  return 0
}

# 把 ffmpeg 的编解码器名映射到 afinfo 会显示的名字，用于结果校验
expected_codec_name() {
  case "$1" in
    opus)  echo "opus" ;;
    aac)   echo "aac" ;;
    alac)  echo "alac" ;;
    pcm_*) echo "lpcm" ;;
    *)     echo "$1" ;;
  esac
}

# ---------------------------------------------------------------------------
# 生成静音文件
# ---------------------------------------------------------------------------
generate() {
  local orig="$1" out="$2"
  local rate ch codec dur
  probe "$orig"
  local rate="$PROBE_RATE" ch="$PROBE_CH" codec="$PROBE_CODEC" dur="$PROBE_DUR"

  # 通道布局参数
  local layout="mono"
  [ "$ch" = "2" ] && layout="stereo"

  echo "${BLD}源文件${RST}  $orig"
  info "格式     ${codec} / ${rate} Hz / ${ch} ch"
  info "时长     ${dur} s"
  info "输出     $out"
  echo

  [ "$(echo "$dur > 0" | bc -l 2>/dev/null || echo 1)" = "1" ] \
    || die "读不到时长，无法生成精确匹配的静音件"

  local tmpdir
  tmpdir="$(mktemp -d)"
  # 用全局变量 + EXIT 清理。不要用 `trap ... RETURN`：在 set -u 下函数返回时
  # 会二次触发，而那时 local 变量已出作用域，会报 unbound variable。
  CLEANUP_DIRS="${CLEANUP_DIRS:-} $tmpdir"

  case "$codec" in
    opus)
      # ffmpeg 无法把 Opus 封装进 CAF，必须用 afconvert
      info "走 afconvert 路径（ffmpeg 不支持 opus@caf）"
      command -v ffmpeg >/dev/null 2>&1 \
        || die "需要 ffmpeg 先生成 PCM 中间文件，但找不到 ffmpeg"

      # 用稍长的 PCM 再裁剪，保证时长精确
      "$ffmpeg_bin" -hide_banner -loglevel error \
        -f lavfi -i "anullsrc=r=${rate}:cl=${layout}" \
        -t "$dur" -c:a pcm_s16le "$tmpdir/mid.wav"

      afconvert -f caff -d opus -c "$ch" "$tmpdir/mid.wav" "$out"
      ;;

    aac)
      command -v ffmpeg >/dev/null 2>&1 || die "需要 ffmpeg 来生成 AAC，请先安装"
      # -f ipod 产出 m4a（AAC in MPEG-4）
      "$ffmpeg_bin" -hide_banner -loglevel error -y \
        -f lavfi -i "anullsrc=r=${rate}:cl=${layout}" \
        -t "$dur" -c:a aac -b:a 32k -f ipod "$out"
      ;;

    alac|lpcm|pcm*|Int16|Int24|Int32|Float32)
      command -v ffmpeg >/dev/null 2>&1 || die "需要 ffmpeg，请先安装"
      local pcmcodec="pcm_s16le"
      [ "$codec" = "Float32" ] && pcmcodec="pcm_f32le"
      "$ffmpeg_bin" -hide_banner -loglevel error -y \
        -f lavfi -i "anullsrc=r=${rate}:cl=${layout}" \
        -t "$dur" -c:a "$pcmcodec" "$out"
      ;;

    *)
      echo
      warn "编解码器 '${codec}' 没有预设的生成路径。"
      info "请手工生成一个 ${rate}Hz / ${ch}ch / ${dur}s 的静音文件，"
      info "编码必须是 ${codec}。然后回到本目录重跑校验。"
      return 1
      ;;
  esac

  # -------------------------------------------------------------------------
  # 校验
  # -------------------------------------------------------------------------
  echo
  [ -s "$out" ] || die "生成失败，输出文件为空"

  local orate och ocodec odur
  probe "$out"
  local orate="$PROBE_RATE" och="$PROBE_CH" ocodec="$PROBE_CODEC" odur="$PROBE_DUR"

  echo "${BLD}校验结果${RST}"
  local pass=1

  if [ "$ocodec" = "$codec" ]; then
    ok "编码      ${ocodec}  （与原件一致）"
  else
    warn "编码      ${ocodec}  ≠ 原件 ${codec}"
    pass=0
  fi

  if [ "$orate" = "$rate" ]; then
    ok "采样率    ${orate} Hz  （与原件一致）"
  else
    warn "采样率    ${orate} Hz  ≠ 原件 ${rate} Hz"
    pass=0
  fi

  if [ "$och" = "$ch" ]; then
    ok "声道      ${och}  （与原件一致）"
  else
    warn "声道      ${och}  ≠ 原件 ${ch}"
    pass=0
  fi

  # AAC 以 1024 帧为一块，时长必然有 <=1 帧的量子化误差（44100Hz 下约 23ms）
  local diff maxdiff
  diff="$(awk -v a="$odur" -v b="$dur" 'BEGIN{d=a-b; if(d<0)d=-d; printf "%.4f", d}')"
  if [ "$ocodec" = "aac" ]; then maxdiff="0.024"; else maxdiff="0.005"; fi

  if awk -v d="$diff" -v m="$maxdiff" 'BEGIN{exit !(d<=m)}'; then
    ok "时长      ${odur} s  vs 原件 ${dur} s  （差 ${diff}s，可接受）"
  else
    warn "时长      ${odur} s  vs 原件 ${dur} s  （差 ${diff}s，超出容差 ${maxdiff}s）"
    pass=0
  fi

  echo
  info "文件      $(ls -la "$out" | awk '{print $5}') 字节"
  info "sha256    $(shasum -a 256 "$out" | cut -d' ' -f1)"
  echo

  if [ "$pass" = "1" ]; then
    echo "${GRN}${BLD}✓ 这个静音件可以直接用于替换${RST}"
  else
    echo "${YEL}${BLD}! 有项目不匹配，建议换一种生成方式再试${RST}"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
main() {
  [ $# -ge 1 ] || {
    echo "用法："
    echo "    $0 <原件文件> [输出文件]"
    echo "    $0 <原件所在目录>          # 批量"
    echo
    echo "说明：读取原件的编码/采样率/声道/时长，生成完全匹配的静音文件。"
    echo "      用于原件与作者 dump 的 original-* 哈希不一致时。"
    exit 2
  }

  local target="$1"

  if [ -d "$target" ]; then
    echo "${BLD}批量模式：$target${RST}"
    echo
    local n=0 fail=0
    while IFS= read -r -d '' f; do
      case "$f" in
        *.m4a|*.caf|*.wav|*.aac|*.mp4|*.aiff|*.aif) ;;
        *) continue ;;
      esac
      # 跳过本脚本自己产出的文件
      case "$(basename "$f")" in
        silent-*|my-silent-*) info "跳过（已是静音件）: $(basename "$f")"; continue ;;
      esac
      n=$((n+1))
      local out
      out="$(dirname "$f")/my-silent-$(basename "$f")"
      generate "$f" "$out" || fail=$((fail+1))
      echo "──────────────────────────────────────────────────────────"
    done < <(find "$target" -maxdepth 1 -type f -print0 | sort -z)

    [ "$n" -gt 0 ] || die "目录里没有找到音频文件"
    echo "${BLD}完成：处理 $n 个，失败 $fail 个${RST}"
    [ "$fail" = "0" ] || exit 1
  else
    [ -f "$target" ] || die "找不到文件：$target"
    local out="${2:-$(dirname "$target")/my-silent-$(basename "$target")}"
    generate "$target" "$out"
  fi
}

main "$@"
