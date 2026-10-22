# 无剪贴板 Unicode 输入调研方案

> 状态：暂无可落地的无剪贴板、无 XCTest 通用 Unicode 方案，调研暂缓；PocketAgent 保留已经实现的 paste、物理键和限定 AX 替换三条输入路径。最后核对：2026-10-22。
> 范围：整理当前协议 findings、独立评审及产品取舍；不将尚未闭合的 createService 研究作为三种现有输入方式的交付前提。

## 1. 需求与关联资料

用户明确本分支的目的就是去掉 XCTest 依赖。目标必须同时满足：不使用剪贴板、支持 Unicode、触发目标 App 正常业务回调、不依赖 XCTest/testmanagerd/XCTestSession 或 UI Automation 授权。不安装 Runner、没有链接 XCTest framework，都不能替代最后一条约束。此前本地 NSXPC 试验虽有真实输入效果，但不满足需求，不能计作本分支交付。

用户随后决定：“如果找不到合理的方案的话就先接受现状 提供剪切板/键盘输入/UI text 替换三种输入方式”。当前没有满足上述全部条件的可用候选，因此采用三路径现状，允许显式、有策略约束的剪贴板输入；无 XCTest 约束保持。三种接口已经存在于 PocketAgent，不表示 ipb 新增了通用 AX 文本产品命令，也不把 AX 回调差异包装成已解决。

- 需求来源：本次用户直接约束；Figma/飞书不涉及。
- 前置：[已确认 AX/P0 结论](ax-p0-research.md)、[原生插入与准入](protocol.md#native-ax-insertion-forwarding-and-remote-admission-2026-10-14)、[宿主 NSXPC 桥接边界](protocol.md#host-to-phone-local-nsxpc-bridge-boundary-2026-10-14)。
- PocketAgent 架构：https://github.com/Borealin/PocketAgent/blob/d93cf052eb954d1f83f0d257af17d291b3453c3f/docs/engineering.md

## 2. 技术调研结论

目前保留的输入手段仍有明确边界：paste 使用剪贴板；AX 整字段替换不能保证普通业务回调；物理键已证明部分 ASCII/拼音候选可行，但未建立任意 Unicode 的确定性最终文本接口。ipb 深层 AX 树能力已经存在，不能把尚未接入 PocketAgent 的观察链描述为 ipb 能力缺失，也不能把接入深树视为解决 Unicode 发送。

手机本地 NSXPC 连接 `com.apple.dt.testmanagerd.runner` 的候选已排除。普通开发签名可以完成 capabilities 交换，但输入要通过 XCTestSession/readiness 及正常 Automation Mode 授权；`_XCT_sendString:maximumFrequency:completion:` 是 XCTest daemon 的接口。独立控件的回调/提交、断连仍继续输入等观察只作为该被排除路线的研究事实保留。PocketAgent 的客户端、工具参数、准备/授权 UI、取消状态机及相关接线全部撤回；不以“实验可选”重新引入依赖。

已有排除结论保持：AXAudit 丢弃 action 的文本 value；APT59 是 getter；普通远程 automation 会话不提供独立于 XCTest 的入口；宿主按 Mach 名请求 socket 也没有取得本地 peer。不再通过变换这些 payload 或添加 Runner 继续同一路线。

普通 App 直接 Recap/IOKit 投递这一分支在匹配 iOS 27.0/24A437 上已收窄为权限阻断：type 0 在连接创建时要求 HID admin bit 0；非零 type 在虚拟服务创建/事件分发接收端要求 event-dispatch bit 3。匹配 IOKit UUID 的普通开发签名准入探针只建连接、不构造或发送事件：type 0 返回本地对象但 server port 为空，type 3/4 有有效 send right。CreateWithType 本身同步调用 Refresh；读 +0x20 的 32 位 port 是该镜像限定的诊断，不能成为产品 ABI，也不能把本地对象非空当作准入。SimpleClient 固定为 type 4，不能把 type 3 标成 Simple。非零分发限制是静态接收端证据，没有声称实机发送被拒。

Apple DDI 自有权限不受上述普通 App 结论直接约束。进一步对照已证实普通 HID `7` 可以令独立 UITextView backing/model 同为 `7` 并触发 `textViewDidChange`，有媒体会话与无媒体会话各一次；该轮真实 Submit 的 AX 动作在发送前被拒，不能计作提交通过。Unicode-page 自定义服务没有取得合法创建回复或存活确认：原始 `createService` 请求无论使用 Unicode page 0x10 还是标准键盘描述符，都触发匹配 dtuhidd 的 RemoteXPC reply-channel 断言；去掉 WANTING_REPLY 后超时、未观察到服务。两次媒体准备超时也发生在创建/发送之前。没有发出 Unicode 输入报告，不能称作 Unicode 输入失败，更不能据此断言 iOS 不支持该 usage page。后续重启调研须先闭合法定创建/回复报文，再查实际文本接收链；不继续盲发同类创建请求。

### createService 报文与回复通道的最后定位

静态来源为 Xcode 27 B6 / CoreDevice 642.15 / Mercury 78 的挂载 DDI `usr/libexec/dtuhidd`，arm64e UUID `87030D25-7165-33AC-99EE-7B7803D100E7`，与 iOS 27.0/24A437 上本轮 crash 匹配。`dyld_info` fixups 与 auth stub/GOT 解析将 crash 前的调用定名，不能仅按相邻 switch 代码猜分支。

| 已核对事实 | 定位与含义 |
| --- | --- |
| create / remove 是不同分支 | GOT `0x100068710` 为 `Request.createService`，`0x100068718` 为 `removeService`；create 从 `0x10002afc4` 跳到 `0x10002b070`，remove 从 `0x10002b06c` 返回 `0x10002b4e4` |
| crash 对应创建结果的回复路径 | create callee 正常返回后到 `0x10002b220`，于 `0x10002b25c` 构造 `CreatedServiceID`，`0x10002b2d4` 调 `XPCObjectEncoder.encode(_:into:)`，无错误时 `0x10002b474` 调 `Mercury.XPCDictionary.sendReply()`；栈中 `0x10002b478` 是下一条指令 |
| 不能据此宣称创建未执行或已成功 | 这是创建结果编码/sendReply 路径，尚未解析实际 reply 对象的来源、合法标志及服务生命周期；服务可能在 daemon 崩溃前有中间状态，未作验收 |
| 删除 WANTING_REPLY 不是已证修复 | create 前存在可选字典检查、缺失时返回的分支。它是 one-way 不产生结果的静态线索，参数来源尚未完全闭合；没有合法成功对照 |
| 客户端没有按流/REPLY 过滤返回对象 | 当前 `pymobiledevice3/remote/remotexpc.py` 的 `receive_response` 返回任意解码出的非空字典，`send_receive_request` 仅串行锁定发送/接收。超时不证明忽略了事件，也不证明没有收到任何底层帧；还未有逐帧关联 capture |

### DeepSeek Flash / Grok 4.7 review 及主循环仲裁

按用户要求，只向两者提供脱敏协议材料，限制为只读、无工具；没有发送配对、签名、设备 ID、私有端点或原始业务文本。Grok 返回元数据为 `grok-4.7-build`；DeepSeek 使用固定 `deepseek-flash` headless profile。两轮意见各自冻结后再由主循环对照源码，模型输出仅为“来源：peer”。两者均未给出已经验证的可用修复。

- **采纳为下一判别式：**对齐合法 producer/receiver 的编码、请求分派、reply 对象与通道，区分共同 descriptor 字段问题和回复构造问题；先完成创建的成功对照，再研究 Unicode 消费者。
- **撤回错误前提：**最初提供的 `ServiceDescriptorMessage` 名称及 wire 形状没有原始依据，已明确撤回并让两者重新评审；不写入产品协议。廉价 reader 曾把 crash 归到 remove 分支，已按完整控制流纠正。
- **不采纳越界推论：**两个 descriptor 同断言不能排除共同字段问题，也不能排除 Unicode 后续不被消费；`receive_response` 超时不能推出“没有数据帧”。两者意见形成时尚无后续完整 stub/控制流定位，不据此声称接收端未命中 create。

当前结论是“创建结果回复路径已定位，根因与可用修正未完成”，而非“Unicode 不支持”或“改成事件消息即可”。这条研究暂缓，不继续触发同类 daemon 崩溃。

仍不得附加 Apple 内部 entitlement、修改安全策略或隐蔽使用剪贴板。指定 Opus 5.5 的技术评审被服务端安全门禁以 `[cyber]` 拒绝；早先自动回落 4.8 的输出仅记为“来源：peer”线索，未计作有效 5.5 独立评审。主循环按原始反汇编和本轮实机结果逐项验真，不以模型标签替代证据。

<details><summary>候选与排除条件</summary>

| 候选 | 当前结论 | 必要判别式 |
| --- | --- | --- |
| 本地/远程 testmanagerd、XCTestSession、Runner | 因产品约束排除 | 不再投入接入/系统密码授权 |
| 普通 App 直接 Recap/IOKit Unicode | 当前匹配接收链受 admin/event-dispatch 权限阻断 | 不再用 type 0 当无权限旁路；不泛化到 DDI 自有权限 |
| DDI 自定义 HID Unicode page | 创建结果回复路径已定位，合法创建/回复协议未闭合；暂缓 | 标准描述符对照同样断言；先核实合法 wire、reply 对象与文本接收链 |
| 现有 HID/IME | 部分按键/候选可用，任意 Unicode 未建立 | 布局、候选、混合文本和提交结果必须可观测、可核验 |
| AX final text | 限定改值能力可用，正常回调不保证 | 不用空格/退格等补事件冒充正常输入 |

拒绝：将“不启动 Runner”等同于“不依赖 XCTest”；将 AX 值匹配等同于业务模型更新；隐藏 paste 或自动切换/重放。
</details>

## 3. 技术方案总括

短期采用 PocketAgent 已有三条输入路径，不增加 method=unicode 或额外授权流程。剪贴板允许/禁止策略和 backend 在入队时冻结，模型及脚本共用执行层验证；禁止后自动改路、未知结果重放或伪造回调。

| 方式 | 产品接口与范围 | 业务/稳定性边界 |
| --- | --- | --- |
| 剪贴板粘贴 | `type_text(method="paste")`；省略/null 保持默认 | 可提交 Unicode，但会替换剪贴板，需策略允许且目标接受 paste；核对实际文本及业务反馈 |
| 键盘输入 | `press_keys`，1–32 物理键与修饰键 | 无剪贴板；受当前布局/IME 限制，候选须真实观察；不承诺任意 Unicode，`input_verified=false` |
| UI text 替换 | `type_text(method="ax", clear=true)`，非空普通 TextField/SearchField | 无剪贴板；fresh AX 值不等于 model/业务确认，排除 TextView/secure/append/empty，不合成补偿事件 |

既有六控件研究的 AX 业务缺口在 UITextView/TextEditor，paste 与物理 ASCII 控制通过；该矩阵不是普适稳定率。键盘分通道、fresh focus、按键释放及无重放机制保持，idle/traffic transport 根因、未 ACK 的 AX 断连、提交后暂不可读和 script stop 后复用仍有边界。只有出现可证明合规的新 sender，才重启静态/实机研究，分别验证 backing、普通回调/model、真实提交、取消与未知结果隔离。

<details><summary>影响、集成与验证</summary>

- PocketAgent：不合目标的接入已经撤回，现有 paste/AX/物理键接口完整保留。用户授权补入 bootstrap 修复和结论文档并合入；[PR #1](https://github.com/Borealin/PocketAgent/pull/1) 已以 `f7a2d3f1c2df9d7dd9b66f2054edca3d5f634a3e` 合入 main。兼容 review 基线为 `d93cf05`，最终补丁只改 host bootstrap、其回归和文档，手机运行代码保持；未引入已排除的 XCTest 候选。产品 review 问题及处置集中于 PocketAgent 的 `docs/devicehub-control.md`，这里不重复归档。
- ipb：本次只覆盖当前研究方案和 verification living section；未增加 Unicode 或通用 AX 文本产品接口，不引入手机端 Runner/服务。
- Android、眼镜 BT/ISP/Wi-Fi、schema、rpc、lt-vad：不受影响；没有眼镜通信或音频契约变化。
- 当前设备状态：上一实机轮 13 Pro 准入/独立控件对照已结束并释放；临时 App 已移除，自有服务不存在，DDI 枚举恢复。原 PocketAgent 安装元数据保持，未操作 12 mini，未改 VPN 或 UI Automation 设置。本次仅静态定位/文档整理，没有新增设备操作、构建或安装，不能新增实机验收声明。
- 原始探针、签名/配对、截图及成功记录保留 Git 外。既有 XCTest 试验不代表本方案验收，不再请求其密码授权。
</details>

## 4. 资源与交付计划

| 模块 | 端/仓库 | 负责人 | 人日 | 分支 | 版本/提测 | 当前状态 | 依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| createService 通路调研 | ipb/开发服务 | Codex 主查；DeepSeek Flash/Grok 4.7 脱敏咨询 | 待确认 | codex/unicode-input-20261021 | 暂缓/未排期 | 创建结果回复路径已定位，根因和修正未闭合；2026-10-22 | 合法创建报文及 reply 对象来源 |
| 新 Unicode 业务回调对照 | 独立 iOS 接收端 | Codex | 待确认 | 同上 | 暂缓/未提测 | 物理 HID 正控成立；Unicode 未发送/未验收 | 合规可用的 Unicode sender |
| 三种既有输入方式 | PocketAgent iOS/native | 维护负责人待确认 | 无新增开发估算 | codex/pr1-compatibility-fixes | 发布/提测待确认 | 接口已实现；bootstrap 修复及文档已随 PR #1 合入 main，保持既有实机验收范围 | 现有策略/目标/回调限制 |
