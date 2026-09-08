
# 独立媒体客户端 9005 攻坚评审（Codex gpt-6-astra，2026-09-08）

brief: scratchpad/astra_9005_brief.md。以下为原文（本轮结论直接促成 RTP 打通）。

**需拍板**

本轮没有需要你拍板的新路线。继续自有进程方案，先修正两处已经由反汇编确认的偏差：

1. **`ClientSessionID` 应是 `CodableValue.uuid(Foundation.UUID)`，线上的载荷是原生 XPC UUID。当前发送的是 String。**
2. **AVC mode 2 是 AirPlay Mirroring；MSS 视频实际使用 mode 5，音频使用 mode 6。mode 不是发送／接收方向。**

这两处偏差**根因已明**；它们是否足以消除设备端全部 9005，**尚未验证**。设备端最终 options 的完整合并路径也仍有证据缺口。

已完整阅读 brief、receiver、最新验证记录及上轮评审。以下依据本机二进制重新定位；没有修改文件、运行设备命令或启动 DeviceHub。

**可自助修**

**Q1．MSS 究竟构造了什么 options？**

首先需要区分三个对象：

| 层次 | 对象 | 已确认行为 |
|---|---|---|
| MSS 调用 CoreDevice | `StartRequest.options` | 主屏接收路径只加入 ClientSessionID UUID |
| CoreDevice 转发 action | `MediaStreamStartParameters.options` | 加入传输参数，再合并调用方 options |
| MSS 初始化 AVC | 最终 `streamInitOptions` | 组合协商结果、固定 ClientName、UUID，随后校验 |

主屏路径的确切定位是 MSS **`0x309A8`**，属于 `PrimaryVideoStreamReceiveAVC.activate` 的异步续体。关键序列：

```asm
0x30C5C  bl   0x67994       ; ClientSessionID key getter
0x30C74…0x30C94            ; 从实例字段复制 Foundation.UUID
0x30CA0                    ; 加载 CodableValue.uuid case
0x30CD8                    ; value witness 安装 enum tag
0x30CE0  bl   0x2CB28       ; 构造单项 Dictionary
```

对应常量：

| 内容 | 定位 |
|---|---|
| key getter | MSS GOT `0x7AFC8`，`CoreDevice.DeviceMediaStream.kAVCMediaStreamOptionClientSessionID.getter` |
| key 实现 | CDU `0x377A3C` |
| 实际键名 | CDU 字面量 `0x48F790`：`avcMediaStreamOptionClientSessionID` |
| 值的 case | MSS GOT `0x7B9A0`：`_$s10CoreDevice12CodableValueO4uuidyAC10Foundation4UUIDVcACmFWC` |

该字典经 `0x316EC → 0x4F7D0` 进入共用接收路径，最终：

```asm
0x52764                    ; 取 options
0x52778  stp x27,x19,[sp,#8] ; options、sessionEventChannel
0x527A0  bl  0x67AA4        ; StartRequest.init
```

初始化器 GOT 是 **`0x7B050`**。

因此，对于这里的主屏接收路径，可以还原为：

```swift
options = [
    DeviceMediaStream.kAVCMediaStreamOptionClientSessionID:
        .uuid(clientSessionID)
]
```

**没有把 ClientName、CallID、ClientSessionID 三个字符串一起装入 StartRequest。** 指定 display ID、虚拟外屏路径另外添加显示模式、display ID 或宽高，不能混入主屏的最小请求。

CoreDevice **`MediaStreamFunctions.startMediaStream(with:)`，`0x120DC8`** 随后补充：

| 键 | 值类型 | 构造位置 |
|---|---|---|
| `AVCMediaStreamNegotiatorTransportProtocolType` | `.int` | 默认值生成函数 `0x124E34`，写入 `0x125204` |
| `AVCMediaStreamNegotiatorAccessNetworkType` | `.int` | 写入 `0x1254F8` |

它们来自 UserDefaults 的有效覆盖值或 DeviceInfo 推导；**不是无条件固定为 1**。调用方 options 在 `0x121CB0` 取出，`0x121CEC → 0x123438` 合并，最后 `0x121DBC` 构造实际 action 参数。

UUID 的线编码也已追到底：

```asm
CDU CodableValue.encode UUID 分支：
0x313D4C  mov w8,#0xc       ; uuid CodingKey
0x313D54…0x313D84           ; Foundation.UUID metadata / Encodable witness
0x313DA8                    ; keyed encode

Mercury UUID 特化：
0xC254                     ; Foundation.UUID.uuid getter
0xC260   bl _xpc_uuid_create
0x9DCC   bl _xpc_dictionary_set_uuid
```

正确的 raw XPC 构造应类似：

```c
uuid_t session;
uuid_generate(session);

xpc_object_t cv = xpc_dictionary_create_empty();
xpc_dictionary_set_uuid(cv, "uuid", session);
xpc_dictionary_set_value(
    opts, "avcMediaStreamOptionClientSessionID", cv);
```

`{"uuid": "UUID字符串"}` 仍然不正确。当前 [receiver.m:121](Experiments/videostream/receiver.m:121) 的 `CV_STR` 无论怎样改 `CVKEY`，内部始终调用 `xpc_dictionary_set_string`，因此此前扫描**没有测试真正的 UUID 编码**。

最小验证：先在本地检查该叶节点的 `xpc_get_type(...) == XPC_TYPE_UUID`，再做 CodableValue 的本地编码／解码对照。无需设备即可排除这层错误。

**Q2．判定的是请求 options，还是 offer 重建的 options？**

**已明：`validateAVCStreamOptions` 校验的是最终 AVC 初始化字典，不能把它等同于线上 `StartRequest.options`。设备侧完整来源链未明。**

MSS 校验器入口 **`0x1212C`** 的要求是：

| 最终键 | 来源 | 强制类型／值 |
|---|---|---|
| `avcMediaStreamOptionClientName` | GOT `0x7AFC0` 的 CDU getter；实现 `0x377A58` | String，且必须等于 `CoreDeviceScreenSharing` |
| `avcMediaStreamOptionCallID` | AVC GOT `0x7B9E8`：`_kAVCMediaStreamOptionCallID` | String |
| `avcMediaStreamOptionClientSessionID` | GOT `0x7AFC8` | **Foundation.UUID** |

关键检查：

```asm
0x123FC  bl _swift_dynamicCast  ; ClientName → String
0x12410                        ; 引用 CoreDeviceScreenSharing
0x1241C…0x12458                 ; 字符串比较
0x124B8  bl _swift_dynamicCast  ; CallID → String
0x1251C  bl _swift_dynamicCast  ; ClientSessionID → Foundation.UUID
0x127A4                        ; 共用 Missing… 错误串
```

UUID metadata 经 **GOT `0x7B2B0`，`_$s10Foundation4UUIDVMa`** 取得。名字不匹配、类型转换失败都能进入同一错误路径；该文案**不能证明三个字段同时缺失**。

在宿主 MSS，可以继续看到：

- **`0xD1DC`**：整理 `streamInitOptions`，读取嵌套 `kAVCMediaStreamInitOptions`。
- **`0xDCCC–0xDD00`**：写入固定 `CoreDeviceScreenSharing`。
- **`0xDD04–0xDD74`**：从外层 options 获取并转换 ClientSessionID UUID。
- **`0xDDBC–0xDE18`**：检查嵌套字典的 UUID。
- **`0x1681C → 0xD1DC`，随后 `0x1689C → 0x1212C`**：视频初始化先整理、再校验。

AVC 自身也有明确生成函数：

**`-[AVCMediaStreamNegotiator generateMediaStreamInitOptionsWithError:]`，`0x1BDA843BC`**

```asm
0x1BDA844A8  ldr x2,[x19,#0x40] ; CallID
0x1BDA844B0                     ; _kAVCMediaStreamOptionCallID
0x1BDA844BC  setObject:forKeyedSubscript:

0x1BDA844C0  ldr x0,[x19,#0x80] ; settings
0x1BDA844C4  clientName
0x1BDA844D0                     ; _kAVCMediaStreamOptionClientName
0x1BDA844DC  setObject:forKeyedSubscript:
```

它生成 CallID、settings 的 ClientName、RemoteEndpointInfo；宿主 MSS 后续在 **`0x54238–0x54290`** 补入自身 UUID。

这些证据支持“**协商器生成部分字段，调用方另供 UUID，MSS 整理后校验**”。但本轮没有反汇编设备同 seed 的 daemon，不能把宿主调用图宣称为设备已证实的合并顺序。

因此，**没有依据要求把 ClientSessionID 手工塞进 offer**。

两个候选私有方法也不是遗漏的入口：

- `initWithMode:options:error:`：**`0x1BDA81268`**
- 内部 **`0x1BDA813A0`** 已调用 `processOffererInitOptions:errorReason:`
- **`0x1BDA813B0`** 已调用 `initNegotiatorLocalConfiguration:options:`
- **`0x1BDA813D0`** 已调用 `createOffer`

`initNegotiatorLocalConfiguration:options:` 的第一个显式参数是错误字符串输出指针，不是配置对象。正确使用方式是让初始化器调用这些内部步骤，不再重复调用或当作 offer 注入接口。

**Q3．initWithMode 实际读取哪些键？为什么看起来被忽略？**

先纠正 mode。MSS **`0x13984`** 的协商器创建函数比较 stream type：

```asm
0x13B40  tst  w19,#1
0x13B44  mov  w8,#5
0x13B48  cinc x26,x8,eq     ; video → 5，非 video → 6
...
0x13DBC  mov  x2,x26
0x13DC0  mov  x3,x22
0x13DC4  bl   initWithMode:options:error:
```

AVC settings 工厂 **`0x1BD977B68`** 用 `(mode - 1)` 索引类表 **`0x1E727C030`**。本轮通过本地加载库、只读类表核实：

| mode | Settings 类 |
|---|---|
| 1 | `iPadCompanion` |
| 2 | `AirplayMirroring` |
| 3 | `RemoteCamera` |
| **5** | **`CoreDeviceScreenSharing`** |
| **6** | **`CoreDeviceSystemAudio`** |

所以，之前“mode 2 能走到 9005，因此模式正确”的推断不成立。

共同选项读取函数 **`processOffererInitOptions:errorReason:`，`0x1BDA81620`** 明确读取：

| 键 | 常量地址，AVC 未滑动地址 | 读取后存入 |
|---|---|---|
| `AVCMediaStreamNegotiatorHDRMode` | `0x1F2C4B418` | `self+0x60` |
| `AVCMediaStreamNegotiatorTransportType` | `0x1F2C4B438` | `self+0x68` |
| `AVCMediaStreamNegotiatorTransportProtocolType` | `0x1F2C4B4B8` | `self+0x78` |
| `AVCMediaStreamNegotiatorVideoWidth` | `0x1F2C4B3B8` | `self+0x18` |
| `AVCMediaStreamNegotiatorVideoHeight` | `0x1F2C4B3D8` | `self+0x10` |

这里均调用 `intValue`，应传 NSNumber 整数。不是所有传入值都会表现为 offer 顶层新增键。

此外：

- 基类 **`setUpDirection:withOptions:`，`0x1BD977880`** 读取 `_AVCMediaStreamNegotiatorDirection`，常量槽 **`0x1E727C908`**，调用 `integerValue`。
- **CoreDeviceScreenSharing settings 初始化器 `0x1BD8015D8`** 在 role 1 分支读取 `_AVCMediaStreamNegotiatorAccessNetworkType`，常量槽 **`0x1E727C8F8`**，`0x1BD801674` 调用 `intValue`。
- 当前 mode 2 选择的是另一套 settings。不能用它的结果断言 CoreDevice settings 忽略 AccessNetworkType。
- 上述入口没有把任意 `avcMediaStreamOptionClientName/ClientSessionID/ClientPID` 拷入 offer。

最小验证：本地分别生成 mode 2／5 的 offer，查看 settings 类、方向、transport 字段及生成的 init options；比较解析后的值，**不要只比较 bplist 字节数**。

**Q4．是否漏掉 StartRequest 字段？**

`type="video"`、`direction="output"` 与 MSS 接收路径一致。CDU rawValue getter：

- **`0x370204`**：内部 case 0／1 → `"audio"`／`"video"`。
- **`0x3704DC`**：内部 case 0／1 → `"input"`／`"output"`。

线上仍应发送这些字符串，不应把内部 case 数字直接替换进去。

brief 的 schema 需要限定为 **CoreDevice 的调用 API**。真正转发的参数是：

```text
CoreDeviceUtilities.MediaStreamStartParameters
receiverIP, receiverPort,
senderIP?, senderPort?,
timeout, type, direction, negotiatorOffer,
clientSupportedFeatures, options, sessionEventChannel?
```

证据是 CoreDevice **`0x121DBC`** 调用构造器，GOT **`0x634F38`**；**`0x1222B8`** 再进入 `ActionDeclaration.forward`。

因此：

- `senderIP/senderPort` **确实存在于实际 wire 参数模型**；不能根据 StartRequest 签名断言它们不存在。
- `sessionEventChannel` 是 Optional；目前没有证据把缺省它归因于这个三字段校验错误。
- `timeout=30`、`clientSupportedFeatures=972` 没有出现在上述校验条件中。**本轮未证明 972 是本 seed 的正确完整能力值**，但没有理由先盲扫它。
- 当前硬编码 `senderPort=51000` 不等于已复现 Apple 的参数构造；尚无证据说明它导致 9005。

**已否决**

以下推断被本轮证据否决，或者不足以继续指导实验：

- **“只有 string/int/bool 可解码，uuid 已被排除”**：扫描没有发原生 XPC UUID。
- **“mode 2 是正确接收模式”**：类表和 MSS 调用点均与之矛盾。
- **“offer 大小不变，说明所有 negotiator options 都被忽略”**：TransportProtocolType 有明确读取、写入指令。
- **“必须把三个字段塞进 offer”**：MSS 主屏 StartRequest 只提供 UUID；CallID、ClientName 另有生成路径。
- **“9005 说明三个字段全缺失”**：类型不匹配、ClientName 不等于固定值也会使用该错误。
- **“直接再调两个内部初始化方法即可注入”**：初始化器已经调用，且其中一个参数被误解。

**验证资源**

**Q5．更省事的确定性手段是什么？**

优先做本地类型和对象状态检查；要确定设备实际分支，再拿同 seed 的设备二进制。宿主 disassembly 无法替代后者。

本轮地址对应 arm64e，均为未加 ASLR slide 的地址：

| 二进制 | UUID |
|---|---|
| MSS | `453D200F-15CC-3122-85C5-5E79B6B9C92B` |
| CoreDevice，642.15 | `C837E681-C7B4-372B-8AD0-983F7FAB0776` |
| CoreDeviceUtilities | `B757FCBC-C1CC-3BED-826D-020BD296EE86` |
| AVConference，共享缓存 | `0C061D6D-207C-3C8B-8637-40F6EC880FE1` |
| Mercury，78.0 | `9829ABCF-2925-336B-A9C2-26948AD1F0C4` |

宿主为 macOS 26.5.1／25F80。AVC 可直接用 Xcode 的 `dyld_info -arch arm64e -disassemble` 读取共享缓存，不必先提取。本轮运行时操作仅用于读取常量、类表，没有创建 negotiator 或媒体会话。

**最小实验顺序，以下均未在本轮执行：**

1. **本地 UUID 检查。** 构造单独 `.uuid` 选项，确认叶节点为 `XPC_TYPE_UUID`；本地解码回 Foundation.UUID。失败就停在编码层。
2. **本地 mode 5 检查。** 保留有明确读取证据的整数选项，检查 settings 类和解析后的 offer／init options。先消除 mode 2 偏差。
3. **一次最小真机 start。** 使用 mode 5 offer，主屏 UUID 选项，并补齐 CoreDevice 原本生成的 transport/access 整数参数；记录完整返回。9005 消失只证明越过该校验，不能当作已取得画面。
4. **若仍是同一 9005，停止扫键。** 从匹配设备 DDI 的 daemon／依赖库定位同一错误串，追踪“请求 options 解码 → 协商器生成 → 最终字典 → validator”的数据流。磁盘现有 DDI 镜像可作为候选，但必须先核对 build；必要时用自有本地测试进程观察宿主整理函数，不能冒充设备证据。


Codex session ID: 01a07fa6-e0d8-7c42-b47f-a65c904a406c
Resume in Codex: codex resume 01a07fa6-e0d8-7c42-b47f-a65c904a406c
