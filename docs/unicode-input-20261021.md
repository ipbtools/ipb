# 无剪贴板 Unicode 输入调研方案

> 状态：尚未找到满足无 XCTest 约束的可用 Unicode 方案；testmanagerd 候选及其 PocketAgent 接入已排除、撤回。最后核对：2026-10-21。
> 范围：继续沿 ipb 已有输入研究，证明普通签名下真正不依赖 XCTest 的输入通路。

## 1. 需求与关联资料

用户明确本分支的目的就是去掉 XCTest 依赖。目标必须同时满足：不使用剪贴板、支持 Unicode、触发目标 App 正常业务回调、不依赖 XCTest/testmanagerd/XCTestSession 或 UI Automation 授权。不安装 Runner、没有链接 XCTest framework，都不能替代最后一条约束。此前本地 NSXPC 试验虽有真实输入效果，但不满足需求，不能计作本分支交付。

- 需求来源：本次用户直接约束；Figma/飞书不涉及。
- 前置：[已确认 AX/P0 结论](ax-p0-research.md)、[原生插入与准入](protocol.md#native-ax-insertion-forwarding-and-remote-admission-2026-10-14)、[宿主 NSXPC 桥接边界](protocol.md#host-to-phone-local-nsxpc-bridge-boundary-2026-10-14)。
- PocketAgent 架构：https://github.com/Borealin/PocketAgent/blob/d93cf052eb954d1f83f0d257af17d291b3453c3f/docs/engineering.md

## 2. 技术调研结论

目前保留的输入手段仍有明确边界：paste 使用剪贴板；AX 整字段替换不能保证普通业务回调；物理键已证明部分 ASCII/拼音候选可行，但未建立任意 Unicode 的确定性最终文本接口。ipb 深层 AX 树能力已经存在，不能把尚未接入 PocketAgent 的观察链描述为 ipb 能力缺失，也不能把接入深树视为解决 Unicode 发送。

手机本地 NSXPC 连接 `com.apple.dt.testmanagerd.runner` 的候选已排除。普通开发签名可以完成 capabilities 交换，但输入要通过 XCTestSession/readiness 及正常 Automation Mode 授权；`_XCT_sendString:maximumFrequency:completion:` 是 XCTest daemon 的接口。独立控件的回调/提交、断连仍继续输入等观察只作为该被排除路线的研究事实保留。PocketAgent 的客户端、工具参数、准备/授权 UI、取消状态机及相关接线全部撤回；不以“实验可选”重新引入依赖。

已有排除结论保持：AXAudit 丢弃 action 的文本 value；APT59 是 getter；普通远程 automation 会话不提供独立于 XCTest 的入口；宿主按 Mach 名请求 socket 也没有取得本地 peer。不再通过变换这些 payload 或添加 Runner 继续同一路线。

普通 App 直接 Recap/IOKit 投递这一分支在匹配 iOS 27.0/24A437 上已收窄为权限阻断：type 0 在连接创建时要求 HID admin bit 0；非零 type 在虚拟服务创建/事件分发接收端要求 event-dispatch bit 3。匹配 IOKit UUID 的普通开发签名准入探针只建连接、不构造或发送事件：type 0 返回本地对象但 server port 为空，type 3/4 有有效 send right。CreateWithType 本身同步调用 Refresh；读 +0x20 的 32 位 port 是该镜像限定的诊断，不能成为产品 ABI，也不能把本地对象非空当作准入。SimpleClient 固定为 type 4，不能把 type 3 标成 Simple。非零分发限制是静态接收端证据，没有声称实机发送被拒。

Apple DDI 自有权限不受上述普通 App 结论直接约束。进一步对照已证实普通 HID `7` 可以令独立 UITextView backing/model 同为 `7` 并触发 `textViewDidChange`，有媒体会话与无媒体会话各一次。Unicode-page 自定义服务尚未建立：原始 `createService` 请求无论使用 Unicode page 0x10 还是标准键盘描述符，都触发匹配 dtuhidd 的 RemoteXPC reply-channel 断言；改用 event-channel framing 后超时，未观察到服务。两次媒体准备超时也发生在创建/发送之前。没有发出 Unicode 输入报告，不能称作 Unicode 输入失败，更不能据此断言 iOS 不支持该 usage page。下一步先闭合法定创建/回复报文，再查实际文本接收链；不继续盲发同类创建请求。

仍不得附加 Apple 内部 entitlement、修改安全策略或隐蔽使用剪贴板。指定 Opus 5.5 的技术评审被服务端安全门禁以 `[cyber]` 拒绝；早先自动回落 4.8 的输出仅记为“来源：peer”线索，未计作有效 5.5 独立评审。主循环按原始反汇编和本轮实机结果逐项验真，不以模型标签替代证据。

<details><summary>候选与排除条件</summary>

| 候选 | 当前结论 | 必要判别式 |
| --- | --- | --- |
| 本地/远程 testmanagerd、XCTestSession、Runner | 因产品约束排除 | 不再投入接入/系统密码授权 |
| 普通 App 直接 Recap/IOKit Unicode | 当前匹配接收链受 admin/event-dispatch 权限阻断 | 不再用 type 0 当无权限旁路；不泛化到 DDI 自有权限 |
| DDI 自定义 HID Unicode page | 创建/回复协议未闭合，未发出输入报告 | 标准描述符对照同样断言；先核实合法 wire 与文本接收链 |
| 现有 HID/IME | 部分按键/候选可用，任意 Unicode 未建立 | 布局、候选、混合文本和提交结果必须可观测、可核验 |
| AX final text | 限定改值能力可用，正常回调不保证 | 不用空格/退格等补事件冒充正常输入 |

拒绝：将“不启动 Runner”等同于“不依赖 XCTest”；将 AX 值匹配等同于业务模型更新；隐藏 paste 或自动切换/重放。
</details>

## 3. 技术方案总括

先证明候选的实际接收链、普通签名权限和无 XCTest 依赖，再进入设备实验。未满足这三项前不增加产品方法、准备按钮或授权流程。可用候选须由独立控件分别读取 backing、普通业务回调/model 及真实提交；其取消、焦点、目标身份和未知结果隔离也必须成立。

<details><summary>影响、集成与验证</summary>

- PocketAgent：本轮撤回不合目标的接入，运行代码恢复接入前状态；现有 paste/AX/物理键契约保持。独立 bootstrap 构建修复保留。
- ipb：维护研究与已排除路线；未增加新的 Unicode 产品输入接口，不引入手机端 Runner/服务。
- Android、眼镜 BT/ISP/Wi-Fi、schema、rpc、lt-vad：不受影响；没有眼镜通信或音频契约变化。
- 当前设备状态：本轮重新协调并核对 13 Pro 后完成准入/独立控件对照；临时 App 已移除，自有服务不存在，DDI 枚举恢复。原 PocketAgent 版本/安装路径/数据容器保持，未操作 12 mini，未改 VPN 或 UI Automation 设置。设备释放见本地 handoff。
- 原始探针、签名/配对、截图及成功记录保留 Git 外。既有 XCTest 试验不代表本方案验收，不再请求其密码授权。
</details>

## 4. 资源与交付计划

| 模块 | 端/仓库 | 负责人 | 人日 | 分支 | 版本/提测 | 当前状态 | 依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 无 XCTest 输入通路调研 | ipb/开发服务 | Codex 主查；指定 Opus 5.5 评审被服务拒绝 | 待确认 | codex/unicode-input-20261021 | 待确认 | 普通 App 直发权限分支关闭；DDI 创建/接收未闭合 | 合法创建报文、匹配接收端 |
| 业务回调对照 | 独立 iOS 接收端 | Codex | 待确认 | 同上 | 未提测 | 物理 HID 正控成立；Unicode 未发送/未验收 | 合规可用的 Unicode sender |
| 产品接入 | PocketAgent iOS/native | 待确认 | 待确认 | codex/pr1-compatibility-fixes | 待确认 | 旧候选撤回；无满足约束的待交付实现 | 无 XCTest 可行性先成立 |
