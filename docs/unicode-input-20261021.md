# 无剪贴板 Unicode 输入调研与实现方案

> 状态：正常系统授权及六类独立控件的 Unicode/业务提交已验证；PocketAgent 已实现显式实验方法，四类原生控件共享执行器及取消/未知保护已验证，正式 App 设置页准备/释放及构建、IPA 检查完成。最后核对：2026-10-21。
> 范围：沿 ipb 已有原生插入/会话准入结果继续研究；通路成立后接入 PocketAgent 并实机验收。

## 1. 需求与关联资料

用户要求优先实现不使用剪贴板、能够触发目标 App 正常业务回调的 Unicode 输入。已有六控件对照证明，AX 整字段替换不能保证 UITextView/TextEditor 的业务模型更新，HID/XCTest typing 与 paste 在记录范围内能够更新。当前正常文字输入保留 paste，AX 保留限定整字段用途，物理键保留真实编辑/IME 用途。本次先证明合法接收通路及独立业务效果，再决定产品接口；不从 ACK 推断输入成功。

- 需求来源：本次用户直接授权；Figma/飞书不涉及。
- 前置：[已确认 AX/P0 结论](ax-p0-research.md)、[原生插入与准入](protocol.md#native-ax-insertion-forwarding-and-remote-admission-2026-10-14)、[宿主 NSXPC 桥接边界](protocol.md#host-to-phone-local-nsxpc-bridge-boundary-2026-10-14)。
- PocketAgent 架构：https://github.com/Borealin/PocketAgent/blob/d93cf052eb954d1f83f0d257af17d291b3453c3f/docs/engineering.md

## 2. 技术调研结论

已有结论保持：AXAudit 丢弃 action 的文本 value；APT59 是 getter；普通远程 IDE/control initiation 不等于 AX-capable XCTestSession；宿主按 Mach 名请求 socket 未取得本地 peer。以上路径不重复变换 payload。新的候选由手机自己的开发签名助手进程创建手机本地 NSXPC peer；本轮已验证本地可达性、正常授权后的文字输入与业务回调；它仍依赖 DDI testmanagerd 和系统授权。Opus 5.5 独立核对候选通路和可证伪实验，主循环核验并执行。

本轮已把本地准入与输入授权分开：仅链接 Foundation/UIKit、使用普通开发签名及合法 `get-task-allow` 的独立应用，可以连接 `com.apple.dt.testmanagerd.runner`，建立 `XCTestSession` 并完成 capabilities 交换。初版客户端漏声明 daemon 主动发送的进程状态回调，导致客户端自行取消连接；补上对应导出协议后此问题消失。这推翻的是“普通开发应用无法建立本地 peer”，不改变宿主到手机 Mach 桥此前失败的结论。

随后只读 orientation 调用在 daemon 端明确返回 error 41（未授权 UI testing）。匹配 DDI 的 `allowsUITestControl` 检查 internal-client 或 Automation Mode；开发签名不能跳过后者。旧探针把 reply 写成两个 `id`，又使 NSError 不在 NSXPC 解码允许类内，客户端丢弃错误；必须使用实际 `NSNumber * / NSError *` 类型并将协议错误与系统授权错误分别报告。这一错误已修复；产品验收仍须与独立接收端的可行性验证分开。

候选字符串入口是 `_XCT_sendString:maximumFrequency:completion:`，先过同一 readiness gate，再调用 gesture performer 的 `typeString:keysPerSecond:completion:`；本地 completion 为单个 nullable NSError。该路线不需 client 链接 XCTest framework，也不需独立 `.xctrunner`，但依赖 DDI 中的 XCTest daemon 及系统 UI Automation 授权，不能称为“完全不依赖 XCTest/Automation Mode”。`loadAccessibility` 的 reply 为 BOOL/NSError，`enableAutomationMode` 的 reply 为单 NSError；均已按匹配镜像复核，不能混用 DTX 包装后的 returnValue/error 形式。

显式请求触发真正的系统密码授权页。先前一次在约 320 秒返回 LocalAuthentication -1003；客户端等待上限不能代表系统提示有效期。用户就绪后重新触发并在设备上完成授权，orientation readiness 成功。随后独立 UIKit 单/多行、SwiftUI TextField/TextEditor、Web input/textarea 均通过 Unicode、普通业务回调及实际提交；Web 检查 trusted input 和 UIKit 首响应者，不能只把 DOM activeElement 当系统焦点。SwiftUI backing 不能退回业务模型。Web 内容 AX PID 与宿主不同，验证器使用每次运行的唯一可访问标识，不能错误要求所有 Web 元素属于宿主 PID。

取消实验复现了新的产品阻断：以每秒五字符发送 140 个合成 ASCII 字符，0.8 秒后关闭本地连接，独立接收端仍继续收到全部字符。静态 session invalidate 清理未找到取消 performer/event stream 的明确调用链；运行结果证明断连不是中止输入。PocketAgent 正接入只在设置页准备、每回合租用的显式 Unicode 方法，取消排空当前 completion；超时/断连未知结果必须停用后续手机动作、禁止自动切回助手，并保留本地持久未知标记。首版限制普通可读字段或已识别的空 TextView、非空整字段替换和 256 UTF-16 单元，拒绝 secure/追加/其他未知值、换行、控制字符及功能键。placeholder 和省略值不证明空字段，最终必须核对输入后的非占位实际值。共享 PhoneExecutor 已通过四类 UIKit/SwiftUI 控件的正常回调、业务模型及实际提交；200 字符 Stop 等待终态回包后才切回助手，断连、丢完成回包及进程重启均保持未知隔离。原始材料留在 Git 外，产品设计及问题修复在 PocketAgent 的 devicehub-control.md 维护。

PocketAgent 的 Web 产品试验在输入前被现有 AXChildren 观察缺口阻断：初始树没有网页输入节点，独立接收端未变化。它不推翻六控件底层 sendString 的 Web 成果，也不否定 ipb 已有的 native deep tree；该观察路径尚未接入 PocketAgent。最终 Opus 5.5 静态复查发现 Swift 的宽松 TextField 映射与 native 普通 subrole 判定不一致，可能在拒绝前先清空；产品在清空前增加同源普通字段标记并补映射回归。长字符串期间的 AX 通知累积曾导致 unsubscribe 的 acknowledgement budget 错误，产品在最后目标校验后先关闭自己的 AX 订阅，再发送文字，之后重新观察；同一 Stop 回归已无此警告。

另一候选的 Unicode stream 已追到 Recap/IOKit。匹配服务端对非零连接类型的虚拟 service 创建及通用 event dispatch 检查 `com.apple.private.hid.client.event-dispatch` 对应 bit；当前探针有效签名没有此 key。尚未做直接 Recap 设备输入，不把这条链宣称为可用的免授权替代，也不遗漏 type-zero 分支或通过修改系统策略/附加 Apple 内部 entitlement 来推进。

<details><summary>候选与拒绝原因</summary>

| 候选 | 当前依据 | 下一判别式 |
| --- | --- | --- |
| 手机本地 NSXPC | 正常授权后的独立业务效果已成立；断连仍继续输入 | 共享执行器与取消保护已验证；正式设置页已验证；其他签名/版本矩阵仍待覆盖 |
| 合法远程 automation 序列 | DDI 有保参 handler，但过去 bootstrap 未完成 | 仅在找到新客户端序列/明确 gate 证据后做新控制 |
| 非 usage 的 Unicode 输入事件 | 待核对现有 HID/开发服务真实接口 | 必须找到保留字符串的实际接收链，不能由 selector 或服务广告推断 |

拒绝：AXAudit payload 猜测；AX 改值后空格/退格补回调；把剪贴板或启动 Runner 隐藏为满足无剪贴板 DDI 目标。
</details>

## 3. 技术方案总括

先在隔离开发签名探针中做只读准入，不改动现有助手数据或已安装应用。准入成功后向独立、App 自己拥有的接收端发一次受保护输入，读取实际 backing text、业务模型、回调和本地提交结果。保留焦点/目标/选区检查、串行执行、超时与取消清理；已发动作不重放。产品实现仅在目标契约成立后增加明确路由，现有 paste 默认和 WDA 选择保持。

<details><summary>影响、集成与验证</summary>

- ipb：协议与准入研究；该路线需要手机本地客户端和 XCTest daemon，不能作为现有无手机服务 ipb 的隐式输入实现。
- PocketAgent iOS/native：已接入同一 PhoneExecutor；无模型的实际工具执行器验收已覆盖，真实外部模型自行选择该方法的回合仍未覆盖。
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
| 保参入口与准入调研 | ipb/开发服务 | Codex 主查、Opus 5.5 复核 | 待确认 | codex/unicode-input-20261021 | 待确认 | 本地 peer/正常授权可用；断连继续输入已复现 | 匹配静态映像、已配对设备 |
| Unicode 业务对照 | 独立 iOS 接收端 | 待确认 | 待确认 | 同上 | 待确认 | 六类控件已完成；取消行为已确认 | 可用签名与实际 peer |
| 产品接入与回归 | PocketAgent iOS/native | Codex 实现、Opus 5.5 复核 | 待确认 | codex/pr1-compatibility-fixes | 待确认 | 四类原生控件/取消/未知/重启及正式设置页已验证 | 正常授权、开发签名；Web 观察仍缺口 |
