# openvela AI 眼镜项目 — AI 对话日志归档

> **本目录是归档备份，不参与大赛日志提交。**
> 大赛要求的日志位于 `logs/1214jipai/`（`manifest.json` + `<date>/claude-code__<sid>.jsonl`，
> 由组委会的归集工具导出）。本目录保留了更好读的 Markdown 派生视图与逐字节原始
> JSONL 备份，供自查与复现使用。它原先位于 `logs/1214jipai/` 内，后按 `logs/README.md`
> 「`logs/` 只放 JSONL 本身」的要求整体迁移至 `archive/`。

本目录是对本项目从**环境搭建**到**TFLite Micro 推理 + 语音播报跑通**全过程的
Claude Code 会话日志归档。

> **数据来源与真实性声明**
>
> 全部内容提取自本机真实保存的 Claude Code 会话记录 (`~/.claude/projects/`) 与文件系统上的实际工程文件。
> 归档过程未创建、未引用任何示例、占位或模板数据；
> 每条记录均可回溯到 `raw/` 下对应的原始 JSONL 文件。

## 一、总览

- **会话数**：7
- **原始 JSONL 记录总数**：6,066
- **归一化事件总数**：4,046
- **时间跨度**：2026-08-22 04:23:48 → 2026-09-11 17:34:31（约 20 天）
- **累计 token**：输入 2,818,548 / 输出 2,336,566
- **模型**：`deepseek-v4-pro`（阶段 01）/ `deepseek-v4-flash`（其余阶段）

## 二、覆盖阶段与会话对照

| # | 阶段 | session id | 起止时间 | 活动时长 | 原始记录 | 事件 | 人工指令 |
|---|------|-----------|---------|---------|---------|------|---------|
| 01 | 环境搭建 / 源码下载（repo sync dev-ai-contest-2026） | `e9916e45` | 08-22 04:23 → 08-23 17:35 | 37h11m | 1,713 | 1,021 | 13 |
| 02 | 编译 / QEMU 模拟器 / ai_glasses 摄像头渲染 | `8e52cf5c` | 08-24 03:30 → 08-27 02:52 | 71h21m | 1,790 | 1,313 | 19 |
| 03 | WSL 侧全量编译 + QEMU 验证 ai_glasses（同一项目的 WSL 工作副本） | `0934bd13` | 09-03 15:29 → 09-04 15:18 | 23h48m | 180 | 131 | 1 |
| 04 | 编译进程排查（cmake/ninja/make 残留进程） | `f85d6ff5` | 09-04 18:14 → 09-04 18:16 | 2m | 59 | 40 | 1 |
| 05 | ai_glasses 图像识别 Demo（image_recognition_demo）+ TTS 引入 | `47200fc3` | 09-04 20:04 → 09-04 22:51 | 2h46m | 117 | 77 | 2 |
| 06 | TFLite Micro person_detect 推理 + espeak-ng 语音播报打通 | `e7b298d1` | 09-04 23:44 → 09-08 11:55 | 84h10m | 1,800 | 1,202 | 8 |
| 07 | 本次日志导出会话（元会话，记录本归档动作本身） | `53cb1ef4` | 09-11 16:59 → 09-11 17:34 | 35m | 407 | 262 | 3 |

## 三、原始文件完整性校验（sha256）

`raw/` 下每个文件都是对应转录的**逐字节复制**。生成本 README 时的校验结果：

| # | 备份文件 | 与源文件一致 |
|---|---------|------------|
| 01 | `raw/01_01-环境搭建-repo-sync__e9916e45.jsonl` | ✅ 一致 |
| 02 | `raw/02_02-编译与QEMU摄像头渲染__8e52cf5c.jsonl` | ✅ 一致 |
| 03 | `raw/03_03-WSL全量编译与QEMU验证__0934bd13.jsonl` | ✅ 一致 |
| 04 | `raw/04_04-编译进程排查__f85d6ff5.jsonl` | ✅ 一致 |
| 05 | `raw/05_05-图像识别Demo与TTS__47200fc3.jsonl` | ✅ 一致 |
| 06 | `raw/06_06-TFLiteMicro推理与语音播报__e7b298d1.jsonl` | ✅ 一致 |
| 07 | `raw/07_07-日志导出会话__53cb1ef4.jsonl` | 🔄 生成时一致；该会话仍在写入，随后必然过期（见边界 2） |

校验方式：`python .\archive\1214jipai\_build\verify.py`（重新比对 sha256）。
阶段 01–06 的源会话均已结束，其备份应始终校验为一致；
阶段 07 是**正在进行的会话**，其备份只是导出时刻的快照，源文件在其后仍会继续追加，因此重跑校验对它报“不一致”是**预期行为**，不代表复制出错。

### 各阶段说明

#### 01. 环境搭建 / 源码下载（repo sync dev-ai-contest-2026）

- **session id**：`e9916e45`
- **原始转录**：`~/.claude/projects/E--openvela/e9916e45-2f9a-4209-8ee6-770037bc58e3.jsonl`
- **备份**：`raw/01_01-环境搭建-repo-sync__e9916e45.jsonl`
- **可读版**：`sessions/01_01-环境搭建-repo-sync__e9916e45.md`
- **统计**：1,713 条原始记录 → 1,021 个事件（用户 13 / 助手 300 / 工具 708），token 输入 902,312 / 输出 443,738

本项目最早的一次可查会话。首条指令即
`repo sync -c -j4 --manifest-branch=dev-ai-contest-2026 --manifest-name=openvela.xml`，其后持续处理 sync 失败重试、host 依赖安装与首次编译尝试。

#### 02. 编译 / QEMU 模拟器 / ai_glasses 摄像头渲染

- **session id**：`8e52cf5c`
- **原始转录**：`~/.claude/projects/E--openvela/8e52cf5c-affc-41ed-96bc-8245ee96e7f0.jsonl`
- **备份**：`raw/02_02-编译与QEMU摄像头渲染__8e52cf5c.jsonl`
- **可读版**：`sessions/02_02-编译与QEMU摄像头渲染__8e52cf5c.md`
- **统计**：1,790 条原始记录 → 1,313 个事件（用户 19 / 助手 492 / 工具 802），token 输入 524,454 / 输出 666,862

围绕 `apps/examples/ai_glasses` 的编译与 QEMU 联调，本会话中 `qemu` 出现数百次，是摄像头渲染链路的主要调试阶段。

#### 03. WSL 侧全量编译 + QEMU 验证 ai_glasses（同一项目的 WSL 工作副本）

- **session id**：`0934bd13`
- **原始转录**：`~/.claude/projects/--wsl-localhost-Ubuntu-22-04-home-dev/0934bd13-c87d-4413-8434-69831ddea082.jsonl`
- **备份**：`raw/03_03-WSL全量编译与QEMU验证__0934bd13.jsonl`
- **可读版**：`sessions/03_03-WSL全量编译与QEMU验证__0934bd13.md`
- **统计**：180 条原始记录 → 131 个事件（用户 1 / 助手 46 / 工具 84），token 输入 208,481 / 输出 84,782

本会话的 cwd 是 `\\wsl.localhost\Ubuntu-22.04\home\dev`，内容同为 ai_glasses / `.repo/build_ai_glasses.log`，确认属于同一项目的 WSL 侧工作副本，故一并纳入。

#### 04. 编译进程排查（cmake/ninja/make 残留进程）

- **session id**：`f85d6ff5`
- **原始转录**：`~/.claude/projects/E--openvela/f85d6ff5-60e5-4490-8d6d-374a04ba8c69.jsonl`
- **备份**：`raw/04_04-编译进程排查__f85d6ff5.jsonl`
- **可读版**：`sessions/04_04-编译进程排查__f85d6ff5.md`
- **统计**：59 条原始记录 → 40 个事件（用户 1 / 助手 17 / 工具 22），token 输入 94,033 / 输出 16,988

短会话，排查构建期间残留的 cmake / ninja / make 进程。

#### 05. ai_glasses 图像识别 Demo（image_recognition_demo）+ TTS 引入

- **session id**：`47200fc3`
- **原始转录**：`~/.claude/projects/E--openvela/47200fc3-ecce-41d5-8072-b313c9d79946.jsonl`
- **备份**：`raw/05_05-图像识别Demo与TTS__47200fc3.jsonl`
- **可读版**：`sessions/05_05-图像识别Demo与TTS__47200fc3.md`
- **统计**：117 条原始记录 → 77 个事件（用户 2 / 助手 24 / 工具 51），token 输入 138,470 / 输出 70,354

实现 `image_recognition_demo()`，并开始调研 TTS 方案（探测 espeak-ng / pico2wave 可用性，讨论内置合成器路径）。

#### 06. TFLite Micro person_detect 推理 + espeak-ng 语音播报打通

- **session id**：`e7b298d1`
- **原始转录**：`~/.claude/projects/E--openvela/e7b298d1-b2a8-42b1-9a4a-c015ea675351.jsonl`
- **备份**：`raw/06_06-TFLiteMicro推理与语音播报__e7b298d1.jsonl`
- **可读版**：`sessions/06_06-TFLiteMicro推理与语音播报__e7b298d1.md`
- **统计**：1,800 条原始记录 → 1,202 个事件（用户 8 / 助手 388 / 工具 806），token 输入 699,647 / 输出 940,223

**目标达成会话。** 本会话收尾消息（2026-09-08）明确记录：QEMU 中 ai_glasses 连续跑完 5 帧——每帧从 `/dev/video` 抓帧 → `person_detect` 真实推理（top-1 = person，conf ≈ 0.67）→ 语音播报 + 写 WAV，输出 `real-inference demo done (5 frames)`，无 panic，正常返回 NSH。同一条消息也记录了当时未完成的 #20～#23 事项（导出日志、README 等），本归档即对应其中的 #20。

#### 07. 本次日志导出会话（元会话，记录本归档动作本身）

- **session id**：`53cb1ef4`
- **原始转录**：`~/.claude/projects/E--openvela/53cb1ef4-fdb9-4d38-abc8-88ee5593a94d.jsonl`
- **备份**：`raw/07_07-日志导出会话__53cb1ef4.jsonl`
- **可读版**：`sessions/07_07-日志导出会话__53cb1ef4.md`
- **统计**：407 条原始记录 → 262 个事件（用户 3 / 助手 72 / 工具 187），token 输入 251,151 / 输出 113,619

即触发本目录生成的会话。因导出动作是在该会话进行中执行的，本会话的 Markdown / JSONL 为**导出时刻的快照**，其后仍会继续增长。

## 四、目录结构

```
archive/1214jipai/
├── README.md            ← 本文件
├── complete-log.md      ← 全部 7 个会话按时间戳合并的完整可读日志（主交付物）
├── sessions.json        ← 机器可读的会话索引与统计
├── sessions/            ← 按会话拆分的可读 Markdown
│   ├── 01_…md
│   └── …
├── raw/                 ← 原始 JSONL 备份（逐字节复制，未做任何修改）
│   ├── 01_…jsonl
│   └── …
└── _build/
    ├── export_logs.py   ← 生成本目录的脚本（可重跑以刷新快照）
    └── verify.py        ← 校验 raw/ 与源转录 sha256 是否一致
```

## 五、时间线（关键节点）

| 时间 | 节点 | 出处 |
|------|------|------|
| 2026-08-22 04:23:48 | 首次可查会话开始，执行 `repo sync` 拉取 dev-ai-contest-2026 源码 | 阶段 01 |
| 2026-08-23 → 08-27 | 编译 / QEMU 摄像头渲染联调 | 阶段 02 |
| 2026-09-03 → 09-04 | WSL 侧全量编译 + QEMU 验证 ai_glasses | 阶段 03 |
| 2026-09-04 | `image_recognition_demo` 与 TTS 方案调研 | 阶段 05 |
| 2026-09-08 | **QEMU 中 person_detect 真实推理 5 帧成功（conf ≈ 0.67）+ 语音播报 + 写 WAV，无 panic，正常返回 NSH** | 阶段 06 收尾 |
| 2026-09-11 16:59:28 | 本日志归档会话开始 | 阶段 07 |

## 六、阅读与复现说明

- **想看全过程** → 打开 `complete-log.md`（约 4.5 MB，按时间戳升序，阶段间有分隔标题）。
- **想按会话看** → `sessions/` 下 7 个文件，每个带独立元信息头。
- **需要原始数据 / 自查** → `raw/` 下 JSONL 为逐字节复制的原件，可用 `render-log.py`（随 contest-log-collector skill 提供）重新渲染。

### 处理规则（Markdown 相对于原始 JSONL 的差异）

Markdown 是可读的**派生视图**，`raw/` 才是完整原件。已知差异：

1. 剥离了 harness 注入的 `<system-reminder>` 块（非人机对话内容）；
2. 跳过了 `image` 类型内容块、`progress` / `file-history-snapshot` 等状态记录；
3. 元信息类记录（`summary` / `permission-mode` / `queue-operation`）不参与渲染；
4. **工具调用与工具输出内容未截断**，保持与原始记录一致；
5. 时间戳由 UTC 转换为本机时区（UTC+8）显示。

### 重跑导出

```powershell
python .\archive\1214jipai\_build\export_logs.py
```

脚本会重新扫描 `~/.claude/projects/` 下的同名转录并覆盖本目录（`raw/` 亦会重新复制，因此始终与最新会话一致）。

## 七、已知边界（如实说明）

1. **起点并非绝对起点。** 阶段 01 开始时，用户已处于 `/mnt/e/openvela` 且 `.repo/manifests` 已切到 `dev-ai-contest-2026` 分支，说明 `repo` 工具安装与首次 clone 发生在任何 Claude Code 会话之前，本归档无法覆盖。
2. **阶段 07 为进行中的会话快照，且必然通不过重跑校验。** 该会话即本次导出动作本身，`raw/07_*.jsonl` 是导出那一刻的副本；源转录在其后仍在追加，因此 `verify.py` 对阶段 07 报“不一致”是**预期行为**，不代表复制出错。阶段 01–06 的校验才是判断复制正确性的依据。
3. **有两个跨目录的散落会话已核对排除**：`C--Users-10516/f2395086…` 与 `e---claude/3a2ba609…` 均为 2026-08-21 的 12 秒内无关会话，不含 openvela / ai_glasses / nuttx 等任何项目标记。
4. **阶段 03 的 cwd 位于 WSL**（`\\wsl.localhost\Ubuntu-22.04\home\dev`），依据其内容（ai_glasses、`.repo/build_ai_glasses.log`）判定为同一项目的 WSL 工作副本。
5. **本目录不含 `manifest.json`，赛事格式的日志已另行生成到 `logs/1214jipai/`。** `raw/` 下是**原始 Claude Code 转录**，不是归一化事件，二者形态不同。赛事要求的
   `manifest.json` + `<date>/claude-code__<sid>.jsonl` 由 `snapshot_core`（组委会归集工具的核心
   归一化逻辑）重新生成，位于 `logs/1214jipai/`，与 `raw/` 并存但互不干扰。
   `logs/` 现由官方 `validate-log.py` 校验通过（`✅ ALL OK`，7 个文件 / 4,063 个事件，0 error 0 warning）。

   两处与 `contest-snapshot --backfill` 默认行为的有意差异：
   - `<date>` 取**会话真实的本地开始日期**（2026-08-22 … 2026-09-11），而非导出当天的日期；
   - 只导出本归档登记的这 7 个会话，不做 `~/.claude/projects/` 全量扫描，避免混入无关会话。
