# 无剪贴板 Unicode 输入调研与实现方案

> 状态：设计中，尚无新的可用输入通路。最后核对：2026-10-21。  
> 范围：沿 ipb 已有原生插入/会话准入结果继续研究；通路成立后接入 PocketAgent 并实机验收。

## 1. 需求与关联资料

用户要求优先实现不使用剪贴板、能够触发目标 App 正常业务回调的 Unicode 输入。已有六控件对照证明，AX 整字段替换不能保证 UITextView/TextEditor 的业务模型更新，HID/XCTest typing 与 paste 在记录范围内能够更新。当前正常文字输入保留 paste，AX 保留限定整字段用途，物理键保留真实编辑/IME 用途。本次先证明合法接收通路及独立业务效果，再决定产品接口；不从 ACK 推断输入成功。

- 需求来源：本次用户直接授权；Figma/飞书不涉及。
- 前置：[已确认 AX/P0 结论](ax-p0-research.md)、[原生插入与准入](protocol.md#native-ax-insertion-forwarding-and-remote-admission-2026-10-14)、[宿主 NSXPC 桥接边界](protocol.md#host-to-phone-local-nsxpc-bridge-boundary-2026-10-14)。
- PocketAgent 架构：https://github.com/Borealin/PocketAgent/blob/d93cf052eb954d1f83f0d257af17d291b3453c3f/docs/engineering.md

## 2. 技术调研结论

已有结论保持：AXAudit 丢弃 action 的文本 value；APT59 是 getter；普通远程 IDE/control initiation 不等于 AX-capable XCTestSession；宿主按 Mach 名请求 socket 未取得本地 peer。以上路径不重复变换 payload。新的候选是由手机自己的开发签名助手进程创建手机本地 NSXPC peer；现有记录未覆盖此路径，其可达性、Automation Mode 条件和输入效果均待验证。Opus 5.5 独立核对候选通路和可证伪实验，主循环核验并执行。

<details><summary>候选与拒绝原因</summary>

| 候选 | 当前依据 | 下一判别式 |
| --- | --- | --- |
| 手机本地 NSXPC | iPhoneOS XCTestCore 的 connectionForInitiatingSharedSession 使用本地 Mach service；DDI 有 XCTestSession/保参 action handler | 普通开发签名探针能否建立实际 peer 并完成只读 RPC；只有成功后测试插入 |
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
- 原始探针、日志、截图、签名/设备信息与成功记录留在 Git 外。无可用路径时记录已排除项、根因程度和未到达的验收阶段，不提交假实现。
</details>

## 4. 资源与交付计划

| 模块 | 端/仓库 | 负责人 | 人日 | 分支 | 版本/提测 | 当前状态 | 依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 保参入口与准入调研 | ipb/开发服务 | 待确认 | 待确认 | codex/unicode-input-20261021 | 待确认 | 研究中；2026-10-21 | 匹配静态映像、已配对设备 |
| Unicode 业务对照 | 独立 iOS 接收端 | 待确认 | 待确认 | 同上 | 待确认 | 准入后执行 | 可用签名与实际 peer |
| 产品接入与回归 | PocketAgent iOS/native | 待确认 | 待确认 | 待可行后确定 | 待确认 | 尚未实现 | 独立业务验收通过 |
