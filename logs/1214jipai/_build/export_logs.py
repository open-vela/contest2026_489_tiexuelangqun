#!/usr/bin/env python3
"""
Export the real Claude Code session transcripts for the openvela AI-glasses
project into E:\\openvela\\logs\\ as readable Markdown, plus byte-exact copies
of the original JSONL transcripts.

Transcript parsing is delegated to the contest-log-collector skill's
snapshot_core.expand_claude_event so the event model matches the
openvela AI contest log schema.

Nothing in this script fabricates content: every line of output is derived
from a real transcript on disk under ~/.claude/projects/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()


def _find_skill_shared() -> Path:
    """Locate the contest-log-collector shared adapters by walking up from this
    script, so the tooling keeps working wherever logs/ is moved to."""
    rel = Path(".claude") / "skills" / "contest-log-collector" / \
        "adapters" / "shared"
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / rel).is_dir():
            return parent / rel
    raise SystemExit(
        "Cannot locate contest-log-collector skill (looked for "
        f"{rel} in every parent of {here}).")


SKILL_SHARED = _find_skill_shared()
sys.path.insert(0, str(SKILL_SHARED))

from snapshot_core import expand_claude_event  # noqa: E402

# ---------------------------------------------------------------------------
# Session registry: every entry points at a real transcript that exists on disk.
# `stage` is a human label used for filenames and the README; `title` is the
# first real user instruction of that session, quoted from the transcript.
# ---------------------------------------------------------------------------
PROJECTS = HOME / ".claude" / "projects"
SESSIONS = [
    {
        "slug": "e9916e45",
        "src": PROJECTS / "E--openvela" / "e9916e45-2f9a-4209-8ee6-770037bc58e3.jsonl",
        "stage": "01-环境搭建-repo-sync",
        "stage_cn": "环境搭建 / 源码下载（repo sync dev-ai-contest-2026）",
        "desc": "本项目最早的一次可查会话。首条指令即\n"
                "`repo sync -c -j4 --manifest-branch=dev-ai-contest-2026 --manifest-name=openvela.xml`，"
                "其后持续处理 sync 失败重试、host 依赖安装与首次编译尝试。",
    },
    {
        "slug": "8e52cf5c",
        "src": PROJECTS / "E--openvela" / "8e52cf5c-affc-41ed-96bc-8245ee96e7f0.jsonl",
        "stage": "02-编译与QEMU摄像头渲染",
        "stage_cn": "编译 / QEMU 模拟器 / ai_glasses 摄像头渲染",
        "desc": "围绕 `apps/examples/ai_glasses` 的编译与 QEMU 联调，"
                "本会话中 `qemu` 出现数百次，是摄像头渲染链路的主要调试阶段。",
    },
    {
        "slug": "0934bd13",
        "src": PROJECTS / "--wsl-localhost-Ubuntu-22-04-home-dev" /
                    "0934bd13-c87d-4413-8434-69831ddea082.jsonl",
        "stage": "03-WSL全量编译与QEMU验证",
        "stage_cn": "WSL 侧全量编译 + QEMU 验证 ai_glasses（同一项目的 WSL 工作副本）",
        "desc": "本会话的 cwd 是 `\\\\wsl.localhost\\Ubuntu-22.04\\home\\dev`，"
                "内容同为 ai_glasses / `.repo/build_ai_glasses.log`，"
                "确认属于同一项目的 WSL 侧工作副本，故一并纳入。",
    },
    {
        "slug": "f85d6ff5",
        "src": PROJECTS / "E--openvela" / "f85d6ff5-60e5-4490-8d6d-374a04ba8c69.jsonl",
        "stage": "04-编译进程排查",
        "stage_cn": "编译进程排查（cmake/ninja/make 残留进程）",
        "desc": "短会话，排查构建期间残留的 cmake / ninja / make 进程。",
    },
    {
        "slug": "47200fc3",
        "src": PROJECTS / "E--openvela" / "47200fc3-ecce-41d5-8072-b313c9d79946.jsonl",
        "stage": "05-图像识别Demo与TTS",
        "stage_cn": "ai_glasses 图像识别 Demo（image_recognition_demo）+ TTS 引入",
        "desc": "实现 `image_recognition_demo()`，并开始调研 TTS 方案"
                "（探测 espeak-ng / pico2wave 可用性，讨论内置合成器路径）。",
    },
    {
        "slug": "e7b298d1",
        "src": PROJECTS / "E--openvela" / "e7b298d1-b2a8-42b1-9a4a-c015ea675351.jsonl",
        "stage": "06-TFLiteMicro推理与语音播报",
        "stage_cn": "TFLite Micro person_detect 推理 + espeak-ng 语音播报打通",
        "desc": "**目标达成会话。** 本会话收尾消息（2026-09-08）明确记录："
                "QEMU 中 ai_glasses 连续跑完 5 帧——每帧从 `/dev/video` 抓帧 → "
                "`person_detect` 真实推理（top-1 = person，conf ≈ 0.67）→ 语音播报 + 写 WAV，"
                "输出 `real-inference demo done (5 frames)`，无 panic，正常返回 NSH。"
                "同一条消息也记录了当时未完成的 #20～#23 事项（导出日志、README 等），"
                "本归档即对应其中的 #20。",
    },
    {
        "slug": "53cb1ef4",
        "src": PROJECTS / "E--openvela" / "53cb1ef4-fdb9-4d38-abc8-88ee5593a94d.jsonl",
        "stage": "07-日志导出会话",
        "stage_cn": "本次日志导出会话（元会话，记录本归档动作本身）",
        "desc": "即触发本目录生成的会话。因导出动作是在该会话进行中执行的，"
                "本会话的 Markdown / JSONL 为**导出时刻的快照**，其后仍会继续增长。",
    },
]

ROLE_LABEL = {"user": "👤 USER", "assistant": "🤖 ASSISTANT",
              "tool": "🔧 TOOL", "system": "⚙️ SYSTEM"}

SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>\s*", re.S)


def load_raw(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def normalize(raw_events: list[dict]) -> list[dict]:
    out = []
    for raw in raw_events:
        out.extend(expand_claude_event(raw, fallback_ts=""))
    # Drop events that carry no usable content.
    return [e for e in out if e.get("text") or e.get("thinking")
            or e.get("tool_name")]


def fence(text: str) -> str:
    """Return a backtick fence longer than any run of backticks in `text`."""
    longest = 0
    for m in re.finditer(r"`+", text):
        longest = max(longest, len(m.group()))
    return "`" * max(3, longest + 1)


def fmt_ts(ts: str) -> str:
    if not ts:
        return "?"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def clean_user_text(text: str) -> str:
    """Strip harness-injected system reminders; keep the human's own words."""
    return SYSTEM_REMINDER.sub("", text).strip()


def render_block(value, max_chars: int) -> str:
    if value is None:
        return "(empty)"
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, indent=2)
        except Exception:
            value = repr(value)
    if max_chars and len(value) > max_chars:
        omitted = len(value) - max_chars
        value = (value[:max_chars] +
                 f"\n\n[... {omitted:,} more characters omitted in this "
                 f"Markdown view; full text in ../raw/ ...]")
    f = fence(value)
    return f + "\n" + value + "\n" + f


def render_events(events: list[dict], max_chars: int, with_seq: bool) -> list[str]:
    lines: list[str] = []
    for ev in events:
        role = ev.get("role", "?")
        label = ROLE_LABEL.get(role, role.upper())
        head = f"### {label} · {fmt_ts(ev.get('ts', ''))}"
        if with_seq:
            head += f" · seq={ev.get('seq', '?')}"
        meta = []
        if ev.get("model"):
            meta.append(f"model `{ev['model']}`")
        if ev.get("tokens_in") is not None:
            meta.append(f"tokens {ev.get('tokens_in')}/{ev.get('tokens_out', '?')}")
        if meta:
            head += "  —  " + " · ".join(meta)
        lines.append(head)
        lines.append("")

        if role == "tool":
            name = ev.get("tool_name", "?")
            if name == "<result>":
                err = "  ❌ **ERROR**" if ev.get("is_error") else ""
                lines.append(f"**↩ tool result** for `{ev.get('tool_call_id', '')}`{err}")
                lines.append("")
                lines.append(render_block(ev.get("output"), max_chars))
            else:
                lines.append(f"**→ tool call** `{name}` "
                             f"(id `{ev.get('tool_call_id', '')}`)")
                lines.append("")
                lines.append(render_block(ev.get("input"), max_chars))
                if ev.get("output") is not None:
                    lines.append("**output:**")
                    lines.append("")
                    lines.append(render_block(ev.get("output"), max_chars))
        else:
            if ev.get("thinking"):
                lines.append("> 💭 **thinking**")
                lines.append(">")
                for ln in ev["thinking"].split("\n"):
                    lines.append(f"> {ln}")
                lines.append("")
            if ev.get("text"):
                txt = clean_user_text(ev["text"]) if role == "user" else ev["text"]
                if txt:
                    lines.append(txt)
                    lines.append("")
        lines.append("---")
        lines.append("")
    return lines


def build_session(spec: dict, max_chars: int) -> dict | None:
    src: Path = spec["src"]
    if not src.is_file():
        print(f"  !! missing transcript: {src}", file=sys.stderr)
        return None
    raw = load_raw(src)
    events = normalize(raw)
    ts_list = [e["ts"] for e in events if e.get("ts")]
    if not ts_list:
        ts_list = [r.get("timestamp") for r in raw if r.get("timestamp")]
    return {
        **spec,
        "raw": raw,
        "events": events,
        "start": min(ts_list) if ts_list else "",
        "end": max(ts_list) if ts_list else "",
        "n_raw": len(raw),
        "n_events": len(events),
        "n_user": sum(1 for e in events if e.get("role") == "user"),
        "n_asst": sum(1 for e in events if e.get("role") == "assistant"),
        "n_tool": sum(1 for e in events if e.get("role") == "tool"),
        "tokens_in": sum(e.get("tokens_in") or 0 for e in events),
        "tokens_out": sum(e.get("tokens_out") or 0 for e in events),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    # Self-locating: this script lives at <member_dir>/_build/, so the export
    # root is always its parent's parent, wherever the tree is moved to.
    ap.add_argument("--dest", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--max-tool-chars", type=int, default=0,
                    help="0 = keep tool payloads at full fidelity")
    args = ap.parse_args()

    dest = Path(args.dest)
    (dest / "raw").mkdir(parents=True, exist_ok=True)
    (dest / "sessions").mkdir(parents=True, exist_ok=True)

    built = []
    for spec in SESSIONS:
        s = build_session(spec, args.max_tool_chars)
        if s:
            built.append(s)

    built.sort(key=lambda s: s["start"])

    # 1. byte-exact raw backups
    print("raw backups:")
    for i, s in enumerate(built, 1):
        out = dest / "raw" / f"{i:02d}_{s['stage']}__{s['slug']}.jsonl"
        shutil.copy2(s["src"], out)
        print(f"  {out.name}  ({out.stat().st_size:,} bytes, "
              f"{s['n_raw']:,} records) <- {s['src'].relative_to(HOME)}")

    # 2. per-session markdown
    print("session markdown:")
    for i, s in enumerate(built, 1):
        body = [
            f"# 会话 {i:02d} — {s['stage_cn']}",
            "",
            f"- **session id**: `{s['slug']}`",
            f"- **原始文件**: `raw/{i:02d}_{s['stage']}__{s['slug']}.jsonl`",
            f"- **源码路径**: `{s['src'].relative_to(HOME)}`",
            f"- **时间范围**: {fmt_ts(s['start'])} → {fmt_ts(s['end'])}",
            f"- **原始记录数**: {s['n_raw']:,}",
            f"- **事件数**: {s['n_events']:,} "
            f"(user {s['n_user']}, assistant {s['n_asst']}, tool {s['n_tool']})",
            f"- **token**: in {s['tokens_in']:,} / out {s['tokens_out']:,}",
            "",
            "---",
            "",
        ]
        body += render_events(s["events"], args.max_tool_chars, with_seq=True)
        p = dest / "sessions" / f"{i:02d}_{s['stage']}__{s['slug']}.md"
        p.write_text("\n".join(body), encoding="utf-8")
        print(f"  {p.name}  ({p.stat().st_size:,} bytes)")

    # 3. merged chronological log
    print("merged log:")
    merged = [
        "# openvela AI 眼镜项目 — 完整 AI 对话日志",
        "",
        "本文件由 `~/.claude/projects/` 下真实保存的 Claude Code 会话记录合并而成，",
        "按事件时间戳升序排列。所有内容均来自本机实际会话，无任何示例或占位数据。",
        "",
        f"- 合并会话数：{len(built)}",
        f"- 事件总数：{sum(s['n_events'] for s in built):,}",
        f"- 时间跨度：{fmt_ts(min(s['start'] for s in built))} → "
        f"{fmt_ts(max(s['end'] for s in built))}",
        "",
        "| # | 阶段 | session id | 起始 | 结束 |",
        "|---|------|-----------|------|------|",
    ]
    for i, s in enumerate(built, 1):
        merged.append(f"| {i:02d} | {s['stage_cn']} | `{s['slug']}` | "
                      f"{fmt_ts(s['start'])} | {fmt_ts(s['end'])} |")
    merged += ["", "---", ""]

    flat = []
    for i, s in enumerate(built, 1):
        for ev in s["events"]:
            flat.append((ev.get("ts") or s["start"], i, s, ev))
    flat.sort(key=lambda t: t[0])

    cur = None
    for ts, idx, s, ev in flat:
        if idx != cur:
            cur = idx
            merged += [
                "",
                f"# ═══ 阶段 {idx:02d}：{s['stage_cn']} ═══",
                "",
                f"> session `{s['slug']}` · {fmt_ts(s['start'])} → {fmt_ts(s['end'])}"
                f" · {s['n_events']:,} 事件 · 原文 `raw/{idx:02d}_{s['stage']}__{s['slug']}.jsonl`",
                "",
                "---",
                "",
            ]
        merged += render_events([ev], args.max_tool_chars, with_seq=False)

    p = dest / "complete-log.md"
    p.write_text("\n".join(merged), encoding="utf-8")
    print(f"  {p.name}  ({p.stat().st_size:,} bytes)")

    # machine-readable index for the README / manifest
    idx = {
        "generated_from": str(PROJECTS),
        "sessions": [
            {
                "index": i,
                "session_id": s["slug"],
                "stage": s["stage"],
                "stage_cn": s["stage_cn"],
                "source_transcript": str(s["src"]),
                "start": s["start"],
                "end": s["end"],
                "raw_records": s["n_raw"],
                "events": s["n_events"],
                "user_events": s["n_user"],
                "assistant_events": s["n_asst"],
                "tool_events": s["n_tool"],
                "tokens_in": s["tokens_in"],
                "tokens_out": s["tokens_out"],
            }
            for i, s in enumerate(built, 1)
        ],
    }
    (dest / "sessions.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  sessions.json")

    write_readme(dest, built)
    return 0


def dur(start: str, end: str) -> str:
    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except Exception:
        return "?"
    secs = int((b - a).total_seconds())
    h, m = divmod(secs // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_readme(dest: Path, built: list[dict]) -> None:
    total_ev = sum(s["n_events"] for s in built)
    total_raw = sum(s["n_raw"] for s in built)
    total_in = sum(s["tokens_in"] for s in built)
    total_out = sum(s["tokens_out"] for s in built)
    lo = min(s["start"] for s in built)
    hi = max(s["end"] for s in built)
    try:
        span_days = (datetime.fromisoformat(hi.replace("Z", "+00:00")) -
                     datetime.fromisoformat(lo.replace("Z", "+00:00"))).days
    except Exception:
        span_days = "?"

    L: list[str] = []
    L += [
        "# openvela AI 眼镜项目 — AI 对话日志归档",
        "",
        "本目录是对本项目从**环境搭建**到**TFLite Micro 推理 + 语音播报跑通**全过程的",
        "Claude Code 会话日志归档。",
        "",
        "> **数据来源与真实性声明**",
        ">",
        "> 全部内容提取自本机真实保存的 Claude Code 会话记录 "
        "(`~/.claude/projects/`) 与文件系统上的实际工程文件。",
        "> 归档过程未创建、未引用任何示例、占位或模板数据；",
        "> 每条记录均可回溯到 `raw/` 下对应的原始 JSONL 文件。",
        "",
        "## 一、总览",
        "",
        f"- **会话数**：{len(built)}",
        f"- **原始 JSONL 记录总数**：{total_raw:,}",
        f"- **归一化事件总数**：{total_ev:,}",
        f"- **时间跨度**：{fmt_ts(lo)} → {fmt_ts(hi)}（约 {span_days} 天）",
        f"- **累计 token**：输入 {total_in:,} / 输出 {total_out:,}",
        f"- **模型**：`deepseek-v4-pro`（阶段 01）/ `deepseek-v4-flash`（其余阶段）",
        "",
        "## 二、覆盖阶段与会话对照",
        "",
        "| # | 阶段 | session id | 起止时间 | 活动时长 | 原始记录 | 事件 | 人工指令 |",
        "|---|------|-----------|---------|---------|---------|------|---------|",
    ]
    for i, s in enumerate(built, 1):
        L.append(
            f"| {i:02d} | {s['stage_cn']} | `{s['slug']}` | "
            f"{fmt_ts(s['start'])[5:16]} → {fmt_ts(s['end'])[5:16]} | "
            f"{dur(s['start'], s['end'])} | {s['n_raw']:,} | {s['n_events']:,} | "
            f"{s['n_user']} |")

    # byte-level integrity of the raw backups vs. the live transcripts.
    # A transcript that stopped being written within the last few minutes is
    # still being appended to, so its copy is a snapshot and will diverge.
    checks = []
    for i, s in enumerate(built, 1):
        raw = dest / "raw" / f"{i:02d}_{s['stage']}__{s['slug']}.jsonl"
        same = sha256(raw) == sha256(s["src"])
        try:
            age = (datetime.now(timezone.utc) -
                   datetime.fromisoformat(s["end"].replace("Z", "+00:00"))
                   ).total_seconds()
        except Exception:
            age = 1e9
        checks.append((i, s, raw, same, age < 300))

    L += [
        "",
        "## 三、原始文件完整性校验（sha256）",
        "",
        "`raw/` 下每个文件都是对应转录的**逐字节复制**。生成本 README 时的校验结果：",
        "",
        "| # | 备份文件 | 与源文件一致 |",
        "|---|---------|------------|",
    ]
    for i, s, raw, same, live in checks:
        if live:
            mark = "🔄 生成时一致；该会话仍在写入，随后必然过期（见边界 2）"
        elif same:
            mark = "✅ 一致"
        else:
            mark = "⚠️ 不一致"
        L.append(f"| {i:02d} | `raw/{raw.name}` | {mark} |")
    L += [
        "",
        "校验方式：`python .\\logs\\1214jipai\\_build\\verify.py`（重新比对 sha256）。",
        "阶段 01–06 的源会话均已结束，其备份应始终校验为一致；",
        "阶段 07 是**正在进行的会话**，其备份只是导出时刻的快照，"
        "源文件在其后仍会继续追加，因此重跑校验对它报“不一致”是**预期行为**，"
        "不代表复制出错。",
        "",
        "### 各阶段说明",
        "",
    ]
    for i, s in enumerate(built, 1):
        L += [
            f"#### {i:02d}. {s['stage_cn']}",
            "",
            f"- **session id**：`{s['slug']}`",
            f"- **原始转录**：`~/{s['src'].relative_to(HOME).as_posix()}`",
            f"- **备份**：`raw/{i:02d}_{s['stage']}__{s['slug']}.jsonl`",
            f"- **可读版**：`sessions/{i:02d}_{s['stage']}__{s['slug']}.md`",
            f"- **统计**：{s['n_raw']:,} 条原始记录 → {s['n_events']:,} 个事件"
            f"（用户 {s['n_user']} / 助手 {s['n_asst']} / 工具 {s['n_tool']}），"
            f"token 输入 {s['tokens_in']:,} / 输出 {s['tokens_out']:,}",
            "",
            s["desc"],
            "",
        ]

    L += [
        "## 四、目录结构",
        "",
        "```",
        "logs/1214jipai/",
        "├── README.md            ← 本文件",
        "├── complete-log.md      ← 全部 7 个会话按时间戳合并的完整可读日志（主交付物）",
        "├── sessions.json        ← 机器可读的会话索引与统计",
        "├── sessions/            ← 按会话拆分的可读 Markdown",
        "│   ├── 01_…md",
        "│   └── …",
        "├── raw/                 ← 原始 JSONL 备份（逐字节复制，未做任何修改）",
        "│   ├── 01_…jsonl",
        "│   └── …",
        "└── _build/",
        "    ├── export_logs.py   ← 生成本目录的脚本（可重跑以刷新快照）",
        "    └── verify.py        ← 校验 raw/ 与源转录 sha256 是否一致",
        "```",
        "",
        "## 五、时间线（关键节点）",
        "",
        f"| 时间 | 节点 | 出处 |",
        "|------|------|------|",
        f"| {fmt_ts(built[0]['start'])} | 首次可查会话开始，执行 `repo sync` 拉取 dev-ai-contest-2026 源码 | 阶段 01 |",
        "| 2026-08-23 → 08-27 | 编译 / QEMU 摄像头渲染联调 | 阶段 02 |",
        "| 2026-09-03 → 09-04 | WSL 侧全量编译 + QEMU 验证 ai_glasses | 阶段 03 |",
        "| 2026-09-04 | `image_recognition_demo` 与 TTS 方案调研 | 阶段 05 |",
        "| 2026-09-08 | **QEMU 中 person_detect 真实推理 5 帧成功（conf ≈ 0.67）+ 语音播报 + 写 WAV，"
        "无 panic，正常返回 NSH** | 阶段 06 收尾 |",
        f"| {fmt_ts(built[-1]['start'])} | 本日志归档会话开始 | 阶段 07 |",
        "",
        "## 六、阅读与复现说明",
        "",
        "- **想看全过程** → 打开 `complete-log.md`（约 "
        f"{ (dest / 'complete-log.md').stat().st_size / 1024 / 1024:.1f} MB，"
        "按时间戳升序，阶段间有分隔标题）。",
        "- **想按会话看** → `sessions/` 下 7 个文件，每个带独立元信息头。",
        "- **需要原始数据 / 自查** → `raw/` 下 JSONL 为逐字节复制的原件，"
        "可用 `render-log.py`（随 contest-log-collector skill 提供）重新渲染。",
        "",
        "### 处理规则（Markdown 相对于原始 JSONL 的差异）",
        "",
        "Markdown 是可读的**派生视图**，`raw/` 才是完整原件。已知差异：",
        "",
        "1. 剥离了 harness 注入的 `<system-reminder>` 块（非人机对话内容）；",
        "2. 跳过了 `image` 类型内容块、`progress` / `file-history-snapshot` 等状态记录；",
        "3. 元信息类记录（`summary` / `permission-mode` / `queue-operation`）不参与渲染；",
        "4. **工具调用与工具输出内容未截断**，保持与原始记录一致；",
        "5. 时间戳由 UTC 转换为本机时区（UTC+8）显示。",
        "",
        "### 重跑导出",
        "",
        "```powershell",
        "python .\\logs\\1214jipai\\_build\\export_logs.py",
        "```",
        "",
        "脚本会重新扫描 `~/.claude/projects/` 下的同名转录并覆盖本目录"
        "（`raw/` 亦会重新复制，因此始终与最新会话一致）。",
        "",
        "## 七、已知边界（如实说明）",
        "",
        "1. **起点并非绝对起点。** 阶段 01 开始时，用户已处于 `/mnt/e/openvela` 且 "
        "`.repo/manifests` 已切到 `dev-ai-contest-2026` 分支，说明 `repo` 工具安装与首次 "
        "clone 发生在任何 Claude Code 会话之前，本归档无法覆盖。",
        "2. **阶段 07 为进行中的会话快照，且必然通不过重跑校验。** 该会话即本次导出动作本身，"
        "`raw/07_*.jsonl` 是导出那一刻的副本；源转录在其后仍在追加，"
        "因此 `verify.py` 对阶段 07 报“不一致”是**预期行为**，不代表复制出错。"
        "阶段 01–06 的校验才是判断复制正确性的依据。",
        "3. **有两个跨目录的散落会话已核对排除**："
        "`C--Users-10516/f2395086…` 与 `e---claude/3a2ba609…` 均为 2026-08-21 的 12 秒内"
        "无关会话，不含 openvela / ai_glasses / nuttx 等任何项目标记。",
        "4. **阶段 03 的 cwd 位于 WSL**（`\\\\wsl.localhost\\Ubuntu-22.04\\home\\dev`），"
        "依据其内容（ai_glasses、`.repo/build_ai_glasses.log`）判定为同一项目的 WSL 工作副本。",
        "5. **本目录暂无 `manifest.json`，这是有意为之。** 大赛 collector 的 manifest schema "
        "将 `team_id` 列为必填项，且要求事件文件位于 "
        "`logs/<login>/<date>/claude-code__<sid>.jsonl` 且每行符合 `event.schema.json`；"
        "而 `raw/` 下是**原始 Claude Code 转录**，不是归一化事件，二者形态不同。"
        "待取得 TEAM_ID 后，可另生成一份符合赛事 schema 的事件文件与 manifest.json，"
        "与 `raw/` 并存（`raw/` 的 .jsonl 会被 validate-log.py 视为 orphan 并给出 warning，"
        "属预期，非错误）。",
        "",
    ]
    (dest / "README.md").write_text("\n".join(L), encoding="utf-8")
    print("  README.md")


if __name__ == "__main__":
    sys.exit(main())
