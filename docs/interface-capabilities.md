# 接口能力与规范补充

> 状态：已决定待开发；最后核对：2026-10-27。执行进程：GPT6.1Sol / xhigh / Fast(priority)，方向B。

## 1. 需求与关联资料

用户在2026-10-27授权：与Opus5.5讨论后，设立两个大方向，各由独立GPT6.1Sol/xhigh/Fast进程跟进。基线为main `bf3fcad375db5e11d5573a7ef11fa9a02c8cd1d7` / v0.5.0。产品继续只使用Apple自带服务；不安装手机Runner、不启动XCTest，不把过去版本的实机豁免继承为本次验收。当前两个进程先推进实现和主机回归，实机项保持未验证，未授权自动合入或发布。

ipb已有多个命令族和不同结果语义：发送被接受、实际效果、补充属性失败及清理失败不能互换。目标是明确能力与错误契约，再逐项补充有证据的接口，供脚本、MCP及后续客户端共用。

- 当前来源：[UI指南](ui.md)、[Wire Format](protocol.md)、[独立分发计划](standalone-distribution.md)。
- 方向A：[MCP与agent体验](mcp-agent-experience.md)。
- 截图候选：[pymobiledevice3 v11.10.2 ScreenCaptureService](https://github.com/doronz88/pymobiledevice3/blob/v11.10.2/pymobiledevice3/remote/core_device/screen_capture_service.py#L7-L33)。现有依赖已包含这条实现；源码存在不等于目标设备可用。
- Figma与其他Looktech App/固件/shared协议需求：不涉及；本次只改变ipb主机接口及已存在Apple服务的客户端。

## 2. 技术调研结论

先交付版本化权威契约和维护测试，保持v0.5.0默认CLI、ordinary schema1、deep schema2与退出码兼容。现有 `capabilities --json` 是devicectl透传，保持其含义；新增 `support --json` 表达ipb自己的实现/运行前提/验证范围。MCP进程可先消费旧输出，新增结构化错误通过显式opt-in使用。

<details><summary>证据边界与拒绝方案</summary>

- AX与HID的失败码必须按命令族解释，不能拿全局exit码猜操作是否发送；裸text目前存在剪贴板阶段与粘贴阶段难区分的问题，应以主机可达fixture复现再修。
- pmd ScreenCaptureService经 `com.apple.coredevice.screencaptureservice` / `com.apple.coredevice.feature.capturescreenshot` 返回PNG bytes，未见devicectl/XCTest依赖。首期只做显式Experiments探针和mock验证，不替换正式screenshot；实机前标为source-only/unverified。
- pmd HID keyboard usage codes不等于Unicode，raw createService曾有设备断言线索，不能盲发。slider/picker、多指、文本选择等需确切Apple接口证据与用户可达trigger后另行排期。
- 拒绝方案：把源码/服务广告当已验证；覆盖原capabilities透传语义；用统一成功码或隐式fallback掩盖失败。

</details>

## 3. 技术方案总括

B拥有 `docs/contract.md` 及机器可读契约/fixture、`Sources/ipb_ax.py`和必要的同属接口模块、`bin/ipb`、`scripts/test_ax.py`及新接口测试、`docs/ui.md`、`docs/protocol.md`、`docs/standalone-distribution.md`、`Experiments/rsd-screenshot/`与本方案。`Sources/ax_archive.py`仅在有具体wire证据且必要时改动。A的MCP代码和文档不由B修改。父会话统一处理Makefile/check_host/workflows/Formula/打包/README/docs索引/completions/VERSION，B只提交接线建议。

<details><summary>共享契约、能力状态与集成</summary>


### 已冻结的最小错误对象

共享示例为[docs/contracts/ipb-error-v1.example.json](contracts/ipb-error-v1.example.json)，是待实现的v1契约样例，不是既有产品输出或设备证据。结构固定为kind=ipb.error、contractVersion=1、operation、phase、exitCode、error(type/message)、action、retrySafe、result。

- 枚举未知时明确unknown；读操作action=null，无可保留结果时result=null。动作细节保留not-sent/submitted/accepted/refused、child-exited-zero/nonzero、native-true/false等原生信息，不把它们混成业务成功。
- 非零退出时stdout最多一个ipb.error JSON；保留的完整native结果置于result，原始schema不改。退出0仍原schema1/2。首期结构化错误以Python路径为边界；zsh早期错误可能没有JSON，消费者必须保守兼容。
- retrySafe只表示此操作是否可安全重试；仅只读或可证明not-sent可以true。不能以此自动跳过新的目标/前提校验。signal、returncode<0、>=128、应为JSON却解析失败或信息不足都按unknown。
- A只在kind与contractVersion均匹配时消费v1；转换仍集中于一个适配模块。B维护正式docs/contract.md及契约fixture。

### 契约v1

`docs/contract.md`是唯一权威：逐命令族退出码/分阶段动作状态、单位、缺失/未知字段、超时、取消与重试。沿用原始not-sent/submitted/accepted/refused及input/scroll细节，不把native false或child exit0改成业务成功。输入坐标仍0..1；AX frame为device logical points；时间明确秒/毫秒。

`IPB_ERROR_FORMAT=json`显式开启结构化错误；默认行为不变。失败只输出一个JSON文档；deep full-state失败原本保留的完整树必须保留在错误对象的result字段，不得吞掉或打印两个JSON。正常成功仍输出原schema；新增可忽略字段不改旧语义，改名/删除/语义变化需升版本。字段细节按下文冻结对象实现。缺失信息明确unknown，不从任意stderr文本证明未发送。

### support能力描述

`support --json`使用独立kind与version，不重写Apple capabilities。至少区分实现事实、设备广告/前提以及验证来源。操作状态为verified/unverified/unsupported/unknown，并附范围/原因。verified必须绑定具体host/device/OS/命令范围与证据；单页或补充主机验证不覆盖所有App/完整发布矩阵。查询失败为unknown，不把null advertisement当false。设备探测必须显式选择目标；没有实际探测时不报告available/verified。

### 里程碑与集成顺序

B0：先提交contract与映射fixture，向父会话交付可引用SHA；A可按冻结约定独立实现旧输出适配。B1：Python路径opt-in结构化错误和support元数据/命令；wrapper未知状态保守处理。B2：text分阶段失败与纯RSD截图探针分开提交，更新旧standalone文档的未验证候选，实际设备前不接主命令。后续底层接口增量逐项有据推进。

A/B均只改归属文件，不能自行rebase/cherry-pick/修改对方工作区。交接必须提供commit/file:line与实际测试输出；接线和最终集成由父会话完成。未授权自动合入或发布。

### 验证

主机fixtures覆盖默认输出和退出码golden兼容、opt-in每条可达错误分支、完整native结果保留、字段未知/类型边界、text复制失败/粘贴失败区分、support静态矩阵与查询失败、PNG字节/目标身份的mock验证。与已有89AX回归保持一致。实机待验是structured receipts对应真实阶段、具体seed support以及RSD截图真实返回；本阶段不得操作手机或把主机fixture写成设备验收。

Android/iOS业务App、BT/ISP/Wi-Fi固件、lt-vad/schema/rpc不受影响，原因是其实现和通信契约不在本方向修改范围。

</details>

## 4. 资源与交付计划

| 模块 | 执行 | 分支 | 首次交付 | 依赖 | 人日/版本/提测时间 |
|---|---|---|---|---|---|
| 契约与兼容回归 | 独立GPT6.1Sol进程B；人工负责人待确认 | codex/interface-capabilities | docs/contract.md、固定fixture与首个提交SHA | 当前v0.5.0行为 | 待确认 |
| 结构化错误/text/support | 同一进程B | 同分支分段提交 | 可评审代码、主机测试和接线清单 | B0 | 待确认 |
| RSD截图候选 | 同一进程B | 同分支独立实验提交 | 显式探针与mock验证、设备待办 | 已固定pmd11.10.2；设备验收未安排 | 待确认 |

当前为开发方案，不声称新接口已落地或设备验证完成。
