# Delta Harmonica Studio

[简体中文](README.md) | [English](README.en.md)

Delta Harmonica Studio 是一个 Windows 桌面工具，用于把 MIDI 或单旋律音频转换成可审查的按键时间轴，并导出到 SteelSeries GG、雷蛇、罗技及通用宏工具。

项目本身不会启动游戏、访问游戏进程、发送实时按键或直接修改 GG 的 SQLite 数据库。创建 GG 宏前会显示确认窗口，创建完成后仍需由用户在 GG 中手动绑定按键。导出的 AutoHotkey 脚本只有在用户自行运行后才会发送按键。

## 功能

- 导入 MIDI，查看并选择轨道
- 将 MP3/WAV/FLAC/OGG 中的单旋律自动识别为 MIDI
- 将多声部旋律拒绝或简化为最高音/最低音
- 使用降调（鼠标左键）、半音（中键）、升调（右键）扩展口琴音域；超音域音符可明确选择按八度折叠
- 调整移调、速度、最短按键时间和安全间隔
- 选择导出倍速，在试听进度条上截取片段，并同步查看口琴音孔和键盘动作
- 可选 0–15 毫秒的按键时间微调；仅在有足够间隔时移动整组音符动作，不改变按键保持时长
- 使用 JSON 配置口琴按键映射
- 管理本地歌曲库并批量转换
- 导出 JSON 时间轴、CSV 动作表和 GG API 事件
- 通过本机 GG Engine 创建未绑定宏
- 选择导出雷蛇 Synapse 3 XML、罗技 G HUB Lua、AutoHotkey v2 或通用 JSON
- 在独立窗口中记录桌面按键/鼠标事件，辅助人工验收

## 环境要求

- Windows 10 或 Windows 11
- Python 3.11 或更高版本
- SteelSeries GG（如需修改赛睿的宏，则此条为必须，创建宏时需要正在运行）

当前 Engine 接口适配基于 SteelSeries GG 119 完成验证。该接口不是 SteelSeries 面向第三方发布的稳定 API，GG 升级后可能需要重新验证。

## 安装

在项目根目录打开 PowerShell：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[audio,dev]"
.\.venv\Scripts\python.exe -m pytest
```

如果 `py` 找不到已经安装的 Python，可直接使用 Python 的完整路径执行相同命令。

## 启动

安装完成后，双击根目录中的：

```text
启动_Delta_Harmonica.bat
```

也可以从终端启动：

```powershell
.\.venv\Scripts\python.exe -m dhs
```

## 图形界面用法

1. 点击“导入 MIDI”，也可以点击“导入音频”自动生成 MIDI，或者使用内置三音样本。
2. 选择歌曲和轨道，设置多声部策略、移调、导出倍速等参数。“随机微调 ms”默认为 15，可设为 0 关闭。
   如 MIDI 仍报超音域，可将“超音域处理”改为 `octave_fold`。该选项只把无法演奏的音符按整八度移入可演奏范围，会改变这些音符的实际音高；默认 `reject` 不会自动改谱。
3. 点击“试听预览”可听合成示意音，同时查看口琴音孔、键盘键位和鼠标修饰键的高亮。拖动进度条两端，或在“起点／终点”秒数框中输入时间并点击“应用”，即可试听指定片段。倍速和截取范围会同步到主界面；之后生成的时间轴、GG 宏及外设宏均采用这些设置。点击“恢复全曲”可取消截取。
4. 点击“生成时间轴”仅导出文件。
5. 点击“生成并创建 GG 宏”会先显示确认窗口，然后通过 GG Engine 创建宏。
6. 打开 GG 的宏编辑器，找到以 `DHS_` 开头的新宏并手动绑定。
7. 如需其他设备，在“外设格式”中选择格式，再点击“导出外设宏”。

创建操作不会覆盖现有宏，也不会自动修改设备按键绑定。

试听播放的是从 MIDI 合成的示意音色，不是原 MP3 或游戏内口琴音色；预览仅显示动作，不会向系统发送按键。试听最长 10 分钟；长曲仍可正常转换和导出宏。

随机微调只作用于导出文件，试听仍是基准节奏。一个音符的修饰键、按下和松开会一起移动，按键保持时长不变；间隔不足时自动减小或跳过微调。它不能保证规避任何软件的检测机制，请遵守目标软件的使用规则。

### 各外设格式怎么用

- **雷蛇 Synapse 3（XML）**：在 Synapse 3 的宏模块中导入 XML，再绑定到设备按键。Synapse 3 与 Synapse 4 的宏格式不兼容，本项目当前不宣称支持 Synapse 4。
- **罗技 G HUB（Lua）**：打开设备配置的脚本编辑器，粘贴导出的 Lua 内容。默认以鼠标按钮编号 6（G6）触发，可在文件顶部修改 `TRIGGER_BUTTON`。
- **牧马人/其他外设（AutoHotkey v2）**：安装 AutoHotkey v2，双击导出的 `.ahk` 文件，然后按 F8 播放。之所以采用通用脚本，是因为“牧马人”不同型号的驱动没有统一、公开且可靠的宏导入格式。
- **通用 JSON**：保留毫秒时间轴及 HID 键码，适合第三方软件自行转换。

厂商驱动升级后可能改变导入行为。正式使用前建议先用三音样本测试；导出的脚本不会自动安装或启动第三方软件。

### 音频转 MIDI 的限制

音频识别使用 pYIN 基频检测，适合口琴、哼唱、独奏乐器等较清晰的**单旋律**。完整混音歌曲中的鼓、和弦、多人声会降低准确度，生成后应先检查 MIDI。所有识别均在本机完成，不上传音频。

## 命令行用法

查看 MIDI 轨道：

```powershell
.\.venv\Scripts\python.exe -m dhs inspect .\song.mid
```

转换 MIDI：

```powershell
.\.venv\Scripts\python.exe -m dhs convert .\song.mid --output .\output\song
```

常用选项：

- `--track N`：选择轨道，可重复指定
- `--polyphony reject|highest|lowest`：多声部处理策略
- `--out-of-range reject|octave_fold`：超音域处理，默认拒绝
- `--transpose N`：半音移调
- `--speed N`：速度倍率
- `--min-hold N`：最短按键时长（毫秒）
- `--safe-gap N`：相邻动作安全间隔（毫秒）
- `--clip-start N`、`--clip-end N`：可选，按原始 MIDI 时间（毫秒）截取片段
- `--timing-variation N`：可选，导出时加入 0–15 毫秒的随机微调；命令行默认为 0

只读列出 GG 宏：

```powershell
.\.venv\Scripts\python.exe -m dhs gg-list
```

从已生成的 API 事件文件创建未绑定宏：

```powershell
.\.venv\Scripts\python.exe -m dhs gg-create .\output\song\gg_events.api.json --name "DHS_MySong"
```

音频转 MIDI：

```powershell
.\.venv\Scripts\python.exe -m dhs transcribe .\melody.mp3 --output .\melody.mid
```

从时间轴导出外设宏：

```powershell
.\.venv\Scripts\python.exe -m dhs export-macro .\output\song\timeline.json --format logitech_lua --output .\song.lua --name "DHS_MySong"
```

可选格式为 `razer_synapse3_xml`、`logitech_lua`、`autohotkey_v2`、`generic_json`。

## 输出文件

每次转换会生成：

- `timeline.json`：可读的动作时间轴
- `events.csv`：适合表格检查的动作列表
- `gg_events.api.json`：供本项目提交给 GG Engine 的事件数据
- `gg_events.unverified.json`：保留用于格式研究的旧版候选事件
- `report.json`：转换参数、统计和提示

`gg_events.api.json` 不是可双击导入 GG 的文件，应通过本项目提交。

## 映射配置

默认示例位于 `profiles/harmonica.example.json`。键盘 `Z X C V B N M ,` 对应简谱 `1 2 3 4 5 6 7 高音1`；鼠标左键降一个八度、中键升半音、右键升一个八度。以当前假定的 C4 基准（MIDI 60），可映射的音高为 MIDI 48–85。上述鼠标功能依据[社区项目对口琴控制的整理](https://github.com/LianZiZhou/HarmonicaScript)，基准音高仍需在游戏中逐音校准。

示例映射仅用于演示。正式使用前请根据你的游戏或应用逐个核对音高和键位。

## 安全与隐私

- 不直接读写 GG 数据库中的宏内容
- 不自动创建按键绑定
- 不启动或控制游戏
- 不上传 MIDI、歌曲库或宏数据
- 图形界面的歌曲库和转换输出保存在当前 Windows 用户的本地应用数据目录；命令行输出位置由 `--output` 指定
- `.venv`、缓存、构建产物、数据库文件和 `local-data` 已由 `.gitignore` 排除

创建宏使用 GG 安装时生成的本机证书，只连接 `coreProps.json` 给出的 `127.0.0.1` Engine 地址。项目不会导出或提交证书私钥。

## 开发与测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

源代码位于 `src/dhs`，测试位于 `tests`。GG 请求由 `tools/gg_engine_request.ps1` 完成；它动态查找有效的 SteelSeries 本机证书，不包含固定证书指纹或个人标识符。

## 格式依据

- 音频识别基于 [librosa pYIN](https://librosa.org/doc/latest/generated/librosa.pyin.html)；[librosa 项目](https://github.com/librosa/librosa)提供本机音频分析能力。
- 罗技 Lua 使用 G HUB/LGS 脚本接口中的 `OnEvent`、`PressKey`、`ReleaseKey`、`Sleep` 等调用，参考了社区整理的 [G HUB Lua API 速查表](https://github.com/jehillert/logitech-ghub-lua-cheatsheet)。
- 雷蛇导出采用 [Razer Insider 中的 Synapse 3 XML 样例](https://insider.razer.com/systems-14/fn-key-other-key-customization-14869)及 [GitHub 上的键鼠样例](https://gist.github.com/myl7/085db70b12a75e8973ce3ae082c1365a)；[雷蛇官方说明](https://dl.razerzone.com/videos/transcripts/Transcript_How%20to%20export%20and%20import%20macros%20in%20Razer%20Synapse%204.pdf) Synapse 3 与 4 的宏文件不互通。
- AutoHotkey 格式遵循 [AutoHotkey v2 官方文档](https://www.autohotkey.com/docs/v2/)。

## 当前验收状态

- MIDI 转换：已通过自动测试
- 试听选区与导出时间轴同步：已通过自动测试，包括从持续音中间截取时的按键释放
- 随机微调：已通过按键配对、保持时长与安全间隔测试；不承诺任何反检测效果
- MP3/WAV 单音转 MIDI：已通过合成音频自动测试；真实歌曲准确度取决于音源
- 雷蛇/罗技/AutoHotkey/JSON 导出：已通过文件结构自动测试，尚未在对应厂商驱动及设备中实测
- GG 宏创建与即时回读：已验证
- GG 重启后的持久化：尚未验证
- 设备绑定后的桌面回放：尚未验证

## 许可证

当前仓库未附带开源许可证。在添加许可证前，默认保留全部权利。如果准备接受外部贡献或允许再分发，请先选择并加入合适的 `LICENSE` 文件。
