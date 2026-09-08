# 独立媒体客户端源码评审（Codex gpt-6-astra，2026-09-08）

评审输入：astra_standalone_brief.md + docs/video-stream.md + verification.md + Experiments/videostream。只读。以下为原文。

Turn completed.
**结论：已找到比继续补 Swift bootstrap 更直接的独立客户端路径：原始 RemoteXPC 控制面 + 普通 UDP socket + ObjC `AVCVideoStream`。Apple 自己的 CoreDeviceMediaStreamSupport 就使用这条 socket 入口。** 尚未证明端到端取帧成功，但“传输不可复刻”和“必须先启动 DeviceHub”已不能作为阻断结论。

已完整阅读指定 brief、文档、实验代码和规则。本轮仅检查文件、既有崩溃报告及二进制，未修改文件、运行设备命令或启动 DeviceHub；最终工作区仍干净。

## 需拍板

建议将下一轮独立客户端实验收敛到以下路径：

```text
原始 RemoteXPC：support / start / stop
             ↓ offer / answer
AVCMediaStreamNegotiator
             ↓ configuration + init options
自己的 IPv6 UDP socket
             ↓ XPC dictionary 携带 fd
AVCVideoStream
             ↓
进程内接收、解码回调 → 自己持有的帧
```

**优先验证 ObjC 路径；Swift 客户端保留为 Experiments 中的协议与生命周期参照。** 这符合 rule 2，也不需要先把 DeviceKit 的所有 Swift 类型重建一遍。

这里有两个必须保留的边界：

- “不依赖 DeviceHub.app”有明确实现候选；“完全不依赖 Apple 系统媒体服务”尚未证明。即使媒体会话在本进程，底层 VideoToolbox 解码仍可能使用服务进程。
- 当前只证明了关键构件及调用关系，尚未证明 `RunInProcess` 模式完整支持这组屏幕镜像配置、权限和连续取帧。

你已明确“最终产品不能依赖它常驻”，无需重新讨论 DeviceHub 常驻方案。当前也没有必须由你决定、才能继续定位的根因问题。

## 可自助修

以下简称 CD＝CoreDevice，CDU＝CoreDeviceUtilities，MSS＝CoreDeviceMediaStreamSupport，DK＝DeviceKit。地址均对应本轮二进制；磁盘框架使用未加 ASLR slide 的地址，AVConference 使用共享缓存虚拟地址。

### Q1a：崩溃锁的归属已明，原始崩溃原因仍未明

**那把锁属于 `RemoteDevice._stateStorage`，不是已定位出的某个未初始化全局 coordinator。**

既有 `spike3-2026-09-07-215613.ips` 的 CD 返回地址 `0x2cea4` 对应：

```text
CD 0x2ce78…0x2ce88
  读取 _OBJC_IVAR_$_CoreDevice.RemoteDevice._stateStorage
  从 RemoteDevice 实例取得 stateStorage

CD 0x2cea0
  调用 CDU OSAllocatedUnfairLock.read()
```

该 ivar 的偏移变量位于 CD `0x647248`。进一步追到：

```text
RemoteDevice.init(snapshot:)                  CD 0x12b020
  分配并初始化 ManagedBuffer
  将 buffer 写入同一个 _stateStorage 字段      CD 0x12b31c
```

因此，**锁的对象归属和正常初始化者已明；为何 spike 传到这里的对象/字段无效，仍未明。** 现有栈不足以排除 ABI、`self`、间接返回和对象所有权问题。

尤其有两个值得先查的 ABI 落点：

| 符号 | 静态证据 | 最小验证 |
|---|---|---|
| `MediaStreamSupport.init(device:)`，MSS `0x65608` | 实现包含 `str x0,[x8]`，通过间接结果地址写值 | 检查调用处 `x8` 是否为有效结果存储，构造后内容是否为目标 RemoteDevice |
| `MediaStreamSupport.supportInfo.getter`，MSS `0x65610` | async 入口内部 `ldr x8,[x20]`，需要正确的值类型 `self` 地址 | 检查 getter 的 `self`、RemoteDevice、`_stateStorage` 是否与构造阶段一致 |

[spike.swift:46](Experiments/videostream/spike.swift:46) 手写了 168 字节返回结构。[同文件:49](Experiments/videostream/spike.swift:49) 又自行声明私有构造器。**getter 确实存在 async 实现，但 async 声明正确不等于整个 resilient Swift ABI 正确。**

DeviceKit 的 bootstrap 也可以定位，比“必须依赖 DeviceHub 启动”具体得多：

| 顺序 | 可定位入口与证据 |
|---|---|
| 取得服务连接 | `CoreDeviceService.sharedConnection.getter`，CD `0x5088f0` |
| 创建 manager | `DeviceManager.init(serviceConnection:allowedDeviceVisibilityClasses:)`，CD `0x100ee0` |
| 等待插件加载后的 check-in | `DeviceManager.waitForPostPluginLoadCheckIn()` dispatch thunk，CD `0x10a690` |
| 服务侧 check-in 入口 | `CoreDeviceServiceConnection.sendDeviceManagerCheckInRequest(requestIdentifier:)` dispatch thunk，CD `0x51c160` |
| 注册设备连接 provider | `RemoteDevice.registerConnectionProvider()`，CD `0x342dc` → CDU `ConnectionProviderRegistry.register(...)`，`0xe1bf4` |

DK `DeviceKitContext.current` 的 once initializer `0x6bc834`，实际调用上述 shared connection 和 manager 构造器。其导入绑定分别位于 DK `0x89dce8`、`0x89dc98`。

**context 从 `0x8d2658` 开始，而 manager 存在 `0x8d2680`，即 `+0x28`，不是首个机器字。** 因此先前按首字读取 manager 的实验不能证明 getter 不可独立使用。

现有 C 入口也存在：`_coredevice_xpc_init_services`、`_coredevice_xpc_add_bundle`，Mach-O 符号地址分别为 CD `0xc3fc`、`0xc400`；但不能把调用这两个函数等同于完整 manager/check-in 生命周期。

上述是**静态可复现的候选初始化顺序**，还不能称为已经验证的最小充分 bootstrap。最小实验应先验证构造器与 getter ABI，再做一次正确 manager/check-in 的对照；不要先添加更多“全局初始化”猜测。

### Q1b：可以绕过 MSS 的 Swift 客户端；入口是 `AVCVideoStream`

**`AVCRemoteVideoClient` 是显示附件，不是 RTP 接收端构造器。** MSS 创建媒体流后，才在 `0x57654` 调用它的 `initWithStreamToken:delegate:`。先创建它、再手填 `_videoReceiverConfig`，顺序和层次都不合适。

真正关键的 Apple 调用链是：

```text
MSS VideoStreamAVC.init(localIP:localPort:remoteIP:remotePort:...)
  0x15c3c
    ↓
CDU NetworkUtils.withSharedSocketDictionary(...)
  0x3a6dc8
    ↓
AVCVideoStream initWithNetworkSockets:options:error:
  MSS 调用点 0x16f24
```

CDU 的实现直接证明普通 socket 路径：

```text
NetworkUtils.getSocket(...)                  0x3a4db4
  socket(AF_INET6, SOCK_DGRAM, 0)            0x3a4f38
  SO_REUSEPORT / SO_REUSEADDR / SO_NOSIGPIPE
  bind(...)                                 0x3a52d0

NetworkUtils.getConnectedSocket(...)         0x3a59f0
  connect(...)                              0x3a67a0

NetworkUtils.withSharedSocketDictionary(...) 0x3a6dc8
  xpc_dictionary_set_fd(
      dictionary, "avcKeySharedSocket", fd)  0x3a6e18
  调用接收方
  关闭原始 fd
```

**不需要把 fd 伪装成 NWConnectionClientID，也不需要自行写进 `rtpHandle`。**

`rtpHandle` 的归属同样已明：

- `_RTPCreateHandle`，AVConference `0x1BD6F9C90`，内部 `calloc(1, 0x6c98)`：它是复杂 RTP 上下文，不是整数 fd。
- `-[VCMediaStream createRTPHandleWithStreamConfig:payloadType:localSSRC:]` 在 `0x1BD98F774` 调用它。
- `-[VCMediaStreamTransport setupRTPWithSockets:error:]` 在 `0x1BD9F2BC4` 调用 `_RTPSetSockets(handle, rtpFD, rtcpFD, …)`。
- 相邻还有 `setupRTPWithNWConnection:error:` 路径。两者是不同传输接入方式。

自己的客户端还需补齐完整协商，不能停在 `createOffer`：

```text
createOffer
→ mediastreamstart
→ setAnswer:withError:
→ generateMediaStreamConfigurationWithError:
→ generateMediaStreamInitOptionsWithError:
→ initWithNetworkSockets:options:error:
→ configure:error:
→ setDelegate:
→ start
```

MSS 对后三个协商方法的调用点分别为 `0x141a8`、`0x14724`、`0x14ed8`。其中有明确的 ClientName、CallID、ClientSessionID 校验；不能把协商生成的初始化选项省略为空字典。

现有 [neg_start.m:77](Experiments/videostream/neg_start.m:77) 未在 `bind`/`getsockname` 失败后停止，默认 `utun9`，还固定默认 sender port；[第122行](Experiments/videostream/neg_start.m:122) 最终始终返回零。这些需要先修正实验可信度，才能继续解释 `EADDRNOTAVAIL` 或“没有 RTP”。

**最小验证：**有效隧道地址上成功 bind/getname → 成功 start/answer → 把 connected UDP fd 交给 AVC → 收到解码回调。交接后不能继续用实验中的 `recvfrom` 与 AVC 竞争消费同一个 socket。

### Q1c：权限存在真实检查，但不能从 DeviceHub 权限表推导全部硬门槛

DeviceHub 主二进制确实带有：

- `com.apple.private.coredevice.client`
- `com.apple.videoconference.allow-conferencing`
- `com.apple.QuartzCore.global-capture`
- sandbox、network client/server 和若干 Mach lookup 例外

AVConference 中进一步定位到真实检查：

```text
+[AVConferenceXPCServer(XPCManagement) entitlementStatusForToken:]
  0x1BD9F7288
    SecTaskCreateWithAuditToken
    SecTaskCopyValueForEntitlement
```

权限键解析为 `com.apple.videoconference.allow-conferencing`（键映射来源：peer；检查代码已由主代理复核）。

主代理继续追到事件处理器：

```text
0x1BD9F7D50  取得消息专属 authorizationBlock
0x1BD9F7D88  有则调用该 block
0x1BD9F7FD0  无则检查 entitlement status == 1
0x1BD9F8018  不通过时 xpc_connection_cancel
```

这里 **Boolean true 对应 status 1**。所以这是实际授权门槛，不只是签名元数据；有专属 authorization block 的消息还需按消息分别判断。

| 权限 | 本轮判断 |
|---|---|
| `allow-conferencing` | 已定位进程外 XPC 请求的默认授权检查 |
| `private.coredevice.client` | DeviceHub 持有；未证明当前原始控制面每条请求均强制要求 |
| `QuartzCore.global-capture` | 未证明是接收远端屏幕所必需 |
| Mach lookup、网络权限 | 与是否启用 App Sandbox、实际访问服务有关；不应整包照抄 |

ad-hoc 可以把键写入签名，但**服务通过 audit token 读到并接受这些键，必须另验**。现有 SIP/AMFI 配置不足以单独证明这一层已通过。

最小实验是在后续授权运行时分别记录：签名声明、当前进程 `SecTask` 读值、AVC 初始化结果及服务拒绝日志。只有定位到具体拒绝点，才能决定某权限是否确实挡住所选路径。

### Q2a / Q2b：接收进程可选；已找到具体连续帧回调

AVConference 明确提供：

```text
-[AVCVideoStream shouldRunInProcessWithOptions:]  0x1BDBA1770
  读取 kAVCMediaStreamOptionRunInProcess.boolValue

-[AVCVideoStream configure:error:]               0x1BDBA35C4
  → configureInProcess:error:
  → configureOutOfProcess:error:
```

进程内初始化 `0x1BDD19A4C` 直接创建 `VCVideoStream`，并调用：

```text
setLocalParticipantInfo:networkSockets:withError:
```

因此“RTP/媒体会话一定在 DeviceHub 外”不是架构定律。进程外服务则已由本机 launchd 配置定位：

- 程序：`/usr/libexec/avconferenced`
- Mach services：`com.apple.videoconference.avconference`、`com.apple.videoconference.camera`

**既有 DeviceHub 镜像具体选了哪条路径，仍未明。** `CASlotProxy` 证明显示采用远端渲染对象，单个 hook 未命中不能进一步证明全部解码执行位置。

连续帧已有比猜巨大结构体更好的锚点：

```text
VCVideoStreamReceiver.createDecodeSession:
  0x1BD7D023C
    安装 _decoderFrameCallback

_decoderFrameCallback
  0x1BD7D0F58
    检查状态与 image
    → showDecodedFrame:atTime:                 0x1BD7D0FF4

VCVideoStreamReceiver.showDecodedFrame:atTime:
  0x1BD7D17AC
    → _delegateFunctions 的第二个函数指针      0x1BD7D1860
```

`-[VCVideoStream videoReceiverDelegateFunctions]`，`0x1BDAE3710`，实际提供：

- `_VCVideoStream_DidReceiveSampleBuffer`，`0x1BDAE3734`
- `__VCVideoStream_DidReceiveRemoteFrame`，`0x1BDAE39A0`

所以 C 回调确实是可取帧的位置，但**不能把所有带 sampleBuffer 名字的参数都直接当 CVPixelBuffer**；先核对该回调的实际参数及对象类型。

安全拦截的最小方式是：先记录 receiver 的 PID、实际类和上述函数命中计数；确认后再在创建阶段包装已识别的回调，保留原调用，短暂 retain 帧后交给有界队列处理。当前 arm64e 代码使用 PAC，不能裸拷贝未知结构偏移、随意转换函数签名或运行中并发覆盖表。

让服务“额外发我们一份像素”尚无已定位接口。streamToken/CALayerHost 的附着能力不等于像素订阅；复制 UDP fd 也只会竞争接收，不会复制数据报。注入服务取帧技术上有候选落点，但不应优先于自己创建 AVC 会话。

### Q3a / Q3b：ObjC PULL 入口存在；截图按钮全链尚未恢复

**ObjC 入口就在 `AVCVideoStream` 上：**

```text
-[AVCVideoStream requestLastDecodedFrame]  0x1BDBA4948
```

MSS 也在 `0x19858` 直接发送该 selector。之前只检查 `AVCRemoteVideoClient` 和 receive helper，漏掉了真正的流对象。

但本 seed 有重要限制：

- `RunInProcess == false`：发送异步请求。
- `RunInProcess == true`：记录日志后直接返回。

所以 PULL 适合作为进程外路径的低频兜底，不能直接作为进程内模式的取帧方案。其返回还需按 `stream:didGetLastDecodedFrame:` 的实际 payload 解析，不能假定得到 CVPixelBuffer。

静态分析给不出可靠帧率上限。最小测量从一次在途请求开始，逐步测试 1/5/10/15 Hz，记录回调延迟、实际新帧率、重复帧与积压；这些是测试档位，不是承诺支持的频率。

截图按钮方面，DK 已定位：

- `ScreenshotButtonControl` / `ScreenshotMenuItemProvider`
- `DeviceKit.captureScreenshot` 动作状态机，包含地址 `0x730ac`（来源：peer）
- `CaptureScreenshotProtocol.captureScreenshot(displayUniqueID:)` 导入绑定 `0x89e258`
- `CaptureScreenshotOutput.image` 导入绑定 `0x89f240`，类型是 `CGImageRef`，已复核

这支持**独立 CoreDevice 截图 capability**，不能继续断言按钮必然调用媒体 PULL。SwiftUI 点击闭包到 capability、保存动作的完整 continuation 尚未恢复。最小验证是同时观察 screenshot capability 与 AVC PULL 两个入口，一次点击确定实际调用链；截图 capability 本身是程序化调用候选，无需模拟点击私有 SwiftUI 闭包。

## 已否决

| 旧结论或路径 | 本轮处理 |
|---|---|
| 锁崩溃已证明缺全局 coordinator | 撤回。锁属于 `RemoteDevice._stateStorage`；原始损坏原因未明 |
| `DeviceKitContext.current` 必须由 DeviceHub 启动建立 | 未获证明。已有 once initializer 和具体构造器，旧布局读取不可信 |
| 没有 raw-socket 媒体路径 | 已被 Apple 自己的 `socket → bind → connect → xpc_dictionary_set_fd` 调用链否定 |
| 把 fd 填入 `rtpHandle` | 否决。它是独立分配的 RTP 上下文 |
| 没有 ObjC PULL 入口 | 已否定。入口在 `AVCVideoStream` |
| `CASlotProxy` 加 hook 未命中证明无法连续取帧 | 证据不足；存在进程模式分支及已定位的解码回调 |
| 产品继续增加私有 Swift ABI shim | 维持你已接受的 rule 2 边界，仅限 Experiments |
| 将 DeviceHub 常驻变成最终产品依赖 | 维持你的明确否决 |

这些纠正涉及 [video-stream.md:50](docs/video-stream.md:50)、[video-stream.md:79](docs/video-stream.md:79) 和 [verification.md:327](docs/verification.md:327)、[verification.md:355](docs/verification.md:355)。本轮遵守只读要求，未改写记录。

## 验证资源

本轮证据范围是本机 macOS **26.5.1 / 25F80**、CoreDevice 系列 **642.15**、指定 Xcode 27 beta 6 DeviceKit/DeviceHub，以及本机 AVConference cache。核心 UUID：

| 映像 | UUID |
|---|---|
| CoreDevice | `C837E681-C7B4-372B-8AD0-983F7FAB0776` |
| CoreDeviceMediaStreamSupport | `453D200F-15CC-3122-85C5-5E79B6B9C92B` |
| CoreDeviceUtilities | `B757FCBC-C1CC-3BED-826D-020BD296EE86` |
| DeviceKit | `2630578E-F7F3-3915-AA4C-3C201AD011E7` |
| AVConference | `0C061D6D-207C-3C8B-8637-40F6EC880FE1` |

AVConference 无需提取文件即可继续只读分析：

```sh
/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/dyld_info \
  -disassemble \
  /System/Library/PrivateFrameworks/AVConference.framework/Versions/A/AVConference
```

后续运行验证需要同 seed 主机、可用 iPhone/DDI/隧道，以及独立实验进程。验收应分别记录控制回复、实际 socket 地址、协商配置、AVC 状态、首帧、持续更新和停止释放；只收到数据包或 `rc=0` 都不算拿到屏幕流。

**独立客户端实验顺序：**

1. **修正现有实验的失败传播。** `socket/bind/getsockname/start/answer` 任一步失败即分层退出；取消固定隧道接口和未经验证的端点假设。
2. **验证普通 UDP 传输。** 使用本次有效端点和端口，取得成功 start/answer；把地址绑定问题与媒体问题分开。
3. **完整复刻 ObjC 协商及 fd 交接。** 生成 configuration 和 init options，调用 `initWithNetworkSockets:options:error:`，不构造 `rtpHandle`。
4. **验证 `RunInProcess=true` 的首帧。** 在已定位的 receiver/decoder 回调处观察 PID、类型、时间戳和图像内容；同时保留 configure/start 的真实错误。
5. **验证连续帧与停止。** 连续更新、队列有界、停止后无回调泄漏、socket 和对象释放。若进程内配置不被支持，再用进程外模式做有界对照，仍不启动 DeviceHub。
6. **只针对实际失败验证权限。** 对照服务审计结果定位具体拒绝点，避免先复制整套 entitlement。
7. **Swift ABI/bootstrap 最后做参照实验。** 验证构造器 `x8`、getter `self`、context `+0x28` 和 check-in；不把它重新变成 ObjC 路径的前置条件。


[exited with code 0]
