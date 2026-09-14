---
name: ai-glasses-emulator
description: 在 QEMU ARM64 模拟器中运行 openvela 的 ai_glasses 应用，完成从摄像头抓帧到语音播报的完整 AI 推理流程。触发词：模拟器AI眼镜。Use when running/inspecting the ai_glasses (person_detect) demo on qemu-arm64-v8a-ap.
metadata:
  version: "1.0"
  board: qemu-arm64-v8a-ap
---

# 模拟器AI眼镜 Skill

## 触发词

**模拟器AI眼镜**

## 适用场景

在 QEMU ARM64 模拟器中运行 openvela 的 `ai_glasses` 应用，完成从摄像头抓帧到语音播报的完整 AI 推理流程：

摄像头抓帧 → 降采样灰度化 → TFLite Micro 推理 → 打印置信度 → 生成 WAV → 语音播报。

## 前置条件

- 已进入 `/mnt/e/openvela`（WSL）
- 已执行 `source build/envsetup.sh` 和 `lunch qemu-arm64-v8a-ap`
- 已编译成功（可执行 `.repo/build-ai-glasses.sh`）

> 说明：`build-ai-glasses.sh` 内部实际执行的 lunch 目标是
> `vendor/openvela/boards/vela/configs/qemu-arm64-v8a-ap`，脚本里已封装好，无需手工输入。

## 操作步骤

1. 启动 QEMU：执行 `.repo/run-ai-glasses.sh`
2. 在 NSH 提示符下输入 `ai_glasses`
3. 应用自动从 `/dev/video` 抓取 QVGA RGB565 帧（320x240x2 = 153600 字节）
4. 降采样为 96x96 灰度图
5. 运行 TFLite Micro `person_detect` 模型推理
6. 打印 top-1 类别与置信度
7. 通过 espeak-ng 预渲染的 PCM 生成 WAV，经 nxplayer 进行语音播报

### 脚本细节（实测）

`.repo/build-ai-glasses.sh`：

- 设置 `LD_LIBRARY_PATH=$T/prebuilts/tools/linux/x86_64/lib64`（宿主工具链 aidl/hidl-gen/genromfs 需要）
- `source build/envsetup.sh` → `lunch ...` → `m`
- 日志重定向到 `.repo/build_ai_glasses.log`，末尾追加 `BUILD_EXIT_CODE=`
- 实测构建耗时约 20 分钟；`BUILD_EXIT_CODE=0`

`.repo/run-ai-glasses.sh`：

- QEMU：`-cpu cortex-a53 -machine virt,virtualization=on,gic-version=3 -m 1024`
- 内核：`out/openvela_vela_qemu-arm64-v8a-ap/nuttx`
- 使用 `ivshmem` 共享内存设备（`/dev/shm/my_shmem0`）
- 启动后 `sleep 45` 再向串口输入 `ai_glasses`，之后再 `sleep 150`
- 整体 `timeout 200` 包裹；日志写入 `.repo/ai_glasses_run.log`

## 输出规范

终端每帧打印识别结果，**实际格式**为：

```
ai_glasses: ---- camera frame 4 ----
ai_glasses: captured 153600 bytes from /dev/video
ai_glasses: top-1 = person    conf 0.67  (person 0.67 / notperson 0.33)
ai_glasses: speaking "Person detected"
ai_glasses: speech WAV generated: /data/tts_result.wav (20884 bytes, 10420 samples)
ai_glasses: play via: nxplayer < /data/nxplayer.cmd
```

- 生成 `/data/tts_result.wav`（44 字节 RIFF 头 + 16-bit 单声道 PCM，11025 Hz）
- 播报内容为 `Person detected` 或 `No person detected`
- 结束打印 `ai_glasses: real-inference demo done (5 frames)`

## 关键文件

- `apps/examples/ai_glasses/ai_glasses_main.c` — 主流程、摄像头抓帧、灰度化、WAV 生成、nxplayer 调用
- `apps/examples/ai_glasses/ai_glasses_ml.cpp` — TFLite Micro person_detect 推理（int8, 96x96x1）
- `.repo/build-ai-glasses.sh` — 编译脚本
- `.repo/run-ai-glasses.sh` — 运行脚本

相关配置（`vendor/openvela/boards/vela/configs/qemu-arm64-v8a-ap/defconfig`）：
`CONFIG_EXAMPLES_AI_GLASSES=y`、`CONFIG_TFLITEMICRO=y`、`CONFIG_VIDEO_QEMU_CAMERA=y`

## 验证标准

- 连续跑完 5 帧（`AI_GLASSES_FRAMES = 5`）
- 无 panic
- 正常返回 NSH 提示符 `qemu-armv8a-ap>`

脚本自带的检查项：

```bash
grep -a 'Hello, AI Glasses World' .repo/ai_glasses_run.log   # 启动标志
grep -aiE 'panic|assert|data abort|fatal|dump_assert' .repo/ai_glasses_run.log
tail -15 .repo/ai_glasses_run.log
```

> 脚本以 `timeout 200` 结束 QEMU，因此日志末尾出现
> `qemu-system-aarch64: terminating on signal 15 ... (timeout)` 属正常现象，不是崩溃。

## 已知边界

- **音频不发声**：QEMU 板没有可用声卡，nxplayer 打印 `No suitable Audio Device found`。
  注意此时 nxplayer **仍然返回 0**，所以应用会打印 `playback OK` —— 这个 OK 指的是
  "命令执行完毕"，**不代表真的出声**。音频实际需在主机端取 `/data/tts_result.wav` 播放验证。
- **摄像头是合成图案**：`nuttx/drivers/video/qemu_camera.c` 用生成的 RGB565 测试图案
  填充帧缓冲，不是真实图像，因此每帧置信度是确定性的（实测稳定为 `person 0.67 / notperson 0.33`），
  不能据此判断模型真实精度。
- **TTS 是预渲染的**：识别结果对应的语音在开发主机上由 espeak-ng 预渲染为 PCM 数组，
  编译进固件（`g_pcm_person` / `g_pcm_notperson`），运行时只是套上 RIFF 头写成 WAV，
  应用本身不含运行时 TTS 引擎。
- 当前为模拟器验证，未使用实物硬件。

## 注意

不要写入任何 APIKey、密码等敏感信息。
