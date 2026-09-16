# SteelSeries GG Engine 宏接口记录

本文记录项目当前使用的本机接口和事件结构。它来自对 GG 119 客户端行为的兼容性研究，不是 SteelSeries 发布的公共稳定规范。

## 本机接口

Engine 地址从以下文件的 `encryptedAddress` 字段读取：

```text
C:\ProgramData\SteelSeries\GG\coreProps.json
```

项目使用的端点：

- `GET /macros`：读取宏列表
- `POST /macro/validate`：校验宏名称
- `POST /macro`：创建未绑定宏

请求通过 HTTPS 发送到 `127.0.0.1`，并使用 GG 安装的 SteelSeries 本机证书。GG 119 要求请求头精确为 `Content-Type: application/json`；自动追加 `charset=utf-8` 会导致请求失败。

## 创建请求

创建体包含：

```json
{
  "name": "DHS_Example",
  "events": "[...]",
  "recordingOptions": "{\"delay\":15,\"delayState\":0}"
}
```

`events` 和 `recordingOptions` 都是 JSON 字符串，而不是嵌套对象。

## 事件结构

键盘事件：

```json
{"type":2,"page":1,"code":29,"extraData":1,"timestamp":0}
```

鼠标按钮事件：

```json
{"type":0,"page":0,"code":3,"extraData":0,"timestamp":0}
```

延迟事件：

```json
{"type":4,"page":0,"code":0,"extraData":125,"timestamp":0}
```

字段含义：

- `type=2`：键盘按键
- `type=0`：鼠标按钮
- `type=4`：延迟
- `extraData=1/0`：按下/释放
- 延迟事件的 `extraData`：等待毫秒数
- `code`：对应设备事件的 HID 代码

当前 API 事件不包含旧数据库样本中出现过的 `eventNum` 字段。

## 安全边界

项目只通过 Engine 接口创建未绑定宏，不直接修改 SQLite，不覆盖现有宏，也不自动建立设备按键绑定。GG 更新后应重新执行自动测试和小型人工验收，再用于较长的 MIDI。
