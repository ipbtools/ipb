# 无剪贴板 Unicode 输入调研与实现方案

> 状态：手机本地 NSXPC 会话准入已验证；系统认证超时，等待用户就绪后重新授权。Unicode 业务效果与产品接入尚未成立。最后核对：2026-10-21。
> 范围：沿 ipb 已有原生插入/会话准入结果继续研究；通路成立后接入 PocketAgent 并实机验收。

## 1. 需求与关联资料

用户要求优先实现不使用剪贴板、能够触发目标 App 正常业务回调的 Unicode 输入。已有六控件对照证明，AX 整字段替换不能保证 UITextView/TextEditor 的业务模型更新，HID/XCTest typing 与 paste 在记录范围内能够更新。当前正常文字输入保留 paste，AX 保留限定整字段用途，物理键保留真实编辑/IME 用途。本次先证明合法接收通路及独立业务效果，再决定产品接口；不从 ACK 推断输入成功。

- 需求来源：本次用户直接授权；Figma/飞书不涉及。
- 前置：[已确认 AX/P0 结论](ax-p0-research.md)、[原生插入与准入](protocol.md#native-ax-insertion-forwarding-and-remote-admission-2026-10-14)、[宿主 NSXPC 桥接边界](protocol.md#host-to-phone-local-nsxpc-bridge-boundary-2026-10-14)。
- PocketAgent 架构：https://github.com/Borealin/PocketAgent/blob/d93cf052eb954d1f83f0d257af17d291b3453c3f/docs/engineering.md

## 2. 技术调研结论

已有结论保持：AXAudit 丢弃 action 的文本 value；APT59 是 getter；普通远程 IDE/control initiation 不等于 AX-capable XCTestSession；宿主按 Mach 名请求 socket 未取得本地 peer。以上路径不重复变换 payload。新的候选由手机自己的开发签名助手进程创建手机本地 NSXPC peer；本轮已验证本地可达性，Automation Mode 授权后的输入效果仍待验证。Opus 5.5 独立核对候选通路和可证伪实验，主循环核验并执行。

本轮已把本地准入与输入授权分开：仅链接 Foundation/UIKit、使用普通开发签名及合法 `get-task-allow` 的独立应用，可以连接 `com.apple.dt.testmanagerd.runner`，建立 `XCTestSession` 并完成 capabilities 交换。初版客户端漏声明 daemon 主动发送的进程状态回调，导致客户端自行取消连接；补上对应导出协议后此问题消失。这推翻的是“普通开发应用无法建立本地 peer”，不改变宿主到手机 Mach 桥此前失败的结论。

随后只读 orientation 调用在 daemon 端明确返回 error 41（未授权 UI testing）。匹配 DDI 的 `allowsUITestControl` 检查 internal-client 或 Automation Mode；开发签名不能跳过后者。旧探针把 reply 写成两个 `id`，又使 NSError 不在 NSXPC 解码允许类内，客户端丢弃错误；必须使用实际 `NSNumber * / NSError *` 类型并将协议错误与系统授权错误分别报告。尚无本轮 Unicode 发送、独立业务回调或产品验收结果。

候选字符串入口是 `_XCT_sendString:maximumFrequency:completion:`，先过同一 readiness gate，再调用 gesture performer 的 `typeString:keysPerSecond:completion:`；本地 completion 为单个 nullable NSError。该路线不需 client 链接 XCTest framework，也不需独立 `.xctrunner`，但依赖 DDI 中的 XCTest daemon 及系统 UI Automation 授权，不能称为“完全不依赖 XCTest/Automation Mode”。`loadAccessibility` 的 reply 为 BOOL/NSError，`enableAutomationMode` 的 reply 为单 NSError；均已按匹配镜像复核，不能混用 DTX 包装后的 returnValue/error 形式。

显式请求已触发真正的系统密码授权页。客户端保活等待延长后，系统本次仍在约 320 秒返回 `com.apple.LocalAuthentication/-1003`（认证超时）；客户端超时设置不能被当成系统提示的有效期。已关闭对应本地连接，输入发送次数仍为零。后续只在用户确认能操作手机时发起新请求，不重复使用旧提示。独立六控件接收端和受保护发送探针留在 Git 外；先完成授权、只读 readiness 和独立业务对照，再按用户“可行的话直接实现并实机验证”的授权接入产品。

另一候选的 Unicode stream 已追到 Recap/IOKit。匹配服务端对非零连接类型的虚拟 service 创建及通用 event dispatch 检查 `com.apple.private.hid.client.event-dispatch` 对应 bit；当前探针有效签名没有此 key。尚未做直接 Recap 设备输入，不把这条链宣称为可用的免授权替代，也不遗漏 type-zero 分支或通过修改系统策略/附加 Apple 内部 entitlement 来推进。

<details><summary>候选与拒绝原因</summary>

| 候选 | 当前依据 | 下一判别式 |
| --- | --- | --- |
| 手机本地 NSXPC | 普通开发签名探针已完成 capabilities；未授权 orientation 明确 error 41 | 正常请求 Automation Mode 后能否完成 readiness，再验证独立目标的 Unicode 及业务回调 |
| 合法远程 automation 序列 | DDI 有保参 handler，但过去 bootstrap 未完成 | 仅在找到新客户端序列/明确 gate 证据后做新控制 |
| 非 usage 的 Unicode 输入事件 | 待核对现有 HID/开发服务真实接口 | 必须找到保留字符串的实际接收链，不能由 selector 或服务广告推断 |

拒绝：AXAudit payload 猜测；AX 改值后空格/退格补回调；把剪贴板或启动 Runner 隐藏为满足无剪贴板 DDI 目标。
</details>

## 3. 技术方案总括

先在隔离开发签名探针中做只读准入，不改动现有助手数据或已安装应用。准入成功后向独立、App 自己拥有的接收端发一次受保护输入，读取实际 backing text、业务模型、回调和本地提交结果。保留焦点/目标/选区检查、串行执行、超时与取消清理；已发动作不重放。产品实现仅在目标契约成立后增加明确路由，现有 paste 默认和 WDA 选择保持。

<details><summary>影响、集成与验证</summary>

- ipb：协议与准入研究；产品是否新增输入接口待实验。
- PocketAgent iOS/native：可行后接入同一 PhoneExecutor；先无模型的共享执行器验收，再真实模型回合。
- Android、眼镜 BT/ISP/Wi-Fi、schema、rpc、lt-vad：不受影响；这是 Apple 开发服务输入契约，不涉及眼镜通信或音频。
- 顺序：静态 receiver/权限核对 → 手机本地只读 peer → 无剪贴板 Unicode 独立业务控制 → 产品实现/回归 → iOS build、IPA 检查、同身份/隔离设备验收。
- 验收：UIKit 单行/多行、SwiftUI TextField/TextEditor、Web input/textarea；ASCII、中文、emoji、多行及选区操作按接口真实支持范围逐项验证。secure 值不回显；取消/不确定效果不重放。构建/发送成功单独记录，不能替代业务验收。
- 系统密码只由用户在设备上完成；不修改系统安全策略、无关设置或其他任务的 Runner/daemon。
- 两个会话经用户授权分配设备：本研究独占 13 Pro，ipb 元素/授权对照使用 12 mini；本研究不操作 12 mini。显式启用 Automation Mode 后，13 Pro 先前的 disabled 对照不再代表后续状态。
- 原始探针、日志、截图、签名/设备信息与成功记录留在 Git 外。无可用路径时记录已排除项、根因程度和未到达的验收阶段，不提交假实现。
</details>

## 4. 资源与交付计划

| 模块 | 端/仓库 | 负责人 | 人日 | 分支 | 版本/提测 | 当前状态 | 依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 保参入口与准入调研 | ipb/开发服务 | Codex 主查、Opus 5.5 复核 | 待确认 | codex/unicode-input-20261021 | 待确认 | 本地 peer 已建立；系统授权超时，待用户就绪 | 匹配静态映像、已配对设备 |
| Unicode 业务对照 | 独立 iOS 接收端 | 待确认 | 待确认 | 同上 | 待确认 | 准入后执行 | 可用签名与实际 peer |
| 产品接入与回归 | PocketAgent iOS/native | 待确认 | 待确认 | 待可行后确定 | 待确认 | 尚未实现 | 独立业务验收通过 |
