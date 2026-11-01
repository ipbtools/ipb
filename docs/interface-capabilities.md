# 接口能力与规范补充

> 状态：B0已提交；B1实现与产品接线已完成，设备未验证，待父会话review/提交/PR；最后核对：2026-11-02。执行进程：GPT6.1Sol / xhigh / Fast(priority)，方向B。

## 1. 需求与关联资料

用户授权两个独立GPT6.1Sol/xhigh/Fast方向，基线为main `bf3fcad375db5e11d5573a7ef11fa9a02c8cd1d7` / v0.5.0。2026-11-02的交付范围为完成B1实现与产品接线后由父会话提交并提PR；不自动合入或发布。产品继续只使用Apple自带服务；不安装手机Runner、不启动XCTest，不继承过去版本的实机豁免。本次只做主机回归，不操作手机，设备矩阵仍未运行，不阻止用户请求的PR交付。

ipb已有多个命令族和不同结果语义：发送被接受、实际效果、补充属性失败及清理失败不能互换。目标是明确能力与错误契约，再逐项补充有证据的接口，供脚本、MCP及后续客户端共用。

- 当前来源：[UI指南](ui.md)、[Wire Format](protocol.md)、[独立分发计划](standalone-distribution.md)。
- 方向A：[MCP与agent体验](mcp-agent-experience.md)。
- 截图候选：[pymobiledevice3 v11.10.2 ScreenCaptureService](https://github.com/doronz88/pymobiledevice3/blob/v11.10.2/pymobiledevice3/remote/core_device/screen_capture_service.py#L7-L33)。现有依赖已包含这条实现；源码存在不等于目标设备可用。
- Figma与其他Looktech App/固件/shared协议需求：不涉及；本次只改变ipb主机接口及已存在Apple服务的客户端。

## 2. 技术调研结论

先交付版本化权威契约和维护测试，保持v0.5.0默认CLI、ordinary schema1、deep schema2与退出码兼容。现有 `capabilities --json` 是devicectl透传，保持其含义；新增 `support --json` 表达ipb自己的实现/运行前提/验证范围。MCP进程可先消费旧输出，新增结构化错误通过显式opt-in使用。

<details><summary>证据边界与拒绝方案</summary>

- AX与HID的失败码必须按命令族解释，不能拿全局exit码猜操作是否发送；裸text目前存在剪贴板阶段与粘贴阶段难区分的问题，应以主机可达fixture复现再修。
- pmd ScreenCaptureService是后续独立截图候选，源码存在不等于目标可用。本次不实现探针或替换正式screenshot，不升级固定11.10.2。
- pmd HID keyboard usage codes不等于Unicode，raw createService曾有设备断言线索，不能盲发。slider/picker、多指、文本选择等需确切Apple接口证据与用户可达trigger后另行排期。
- 拒绝方案：把源码/服务广告当已验证；覆盖原capabilities透传语义；用统一成功码或隐式fallback掩盖失败。

</details>

## 3. 技术方案总括

B拥有契约/fixtures、Python AX入口、support模块、bin/ipb及相关接口回归和指南。当前额外授权B在本工作树完成Makefile安装support helper、check_host入口、package_test_build包清单与提取后support启动验证，以及README/docs索引/completions接线。A的MCP文件不修改；ax_archive、AX依赖和Apple wire不变。父会话处理Git提交、PR和CI结果；VERSION/Formula/工作流运行环境不在本次修改范围。

<details><summary>共享契约、能力状态与集成</summary>


### 已冻结的最小错误对象

共享示例为[docs/contracts/ipb-error-v1.example.json](contracts/ipb-error-v1.example.json)，是v1契约示例，不是设备证据。结构固定为kind=ipb.error、contractVersion=1、operation、phase、exitCode、error(type/message)、action、retrySafe、result。

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

B0由父会话提交为 `eda742d`。B1包含Python opt-in错误、静态support和source/install/package接线；包清单明确包含support helper，提取后解析其kind/version，主机总入口纳入现有interface/support回归。父会话review后提交、提PR并检查CI。第一份交接的B1代码保持review baseline；本次没有新增状态/生命周期机制。B2裸text完整结构化阶段与RSD截图不在本次范围。

A/B均只改归属文件，不能自行rebase/cherry-pick/修改对方工作区。B完成本工作树授权的产品接线，跨方向集成与Git/PR/CI由父会话处理；不自动合入或发布。

### 验证

主机回归覆盖三个交付契约：默认/opt-in错误输出兼容与完整native结果保留；source/installed support静态元数据不触发设备查询且capabilities保持旧行为；临时PREFIX安装和归档提取后包含helper并通过support启动检查。既有AX源码与依赖未变，复用对应89项回归，不为接线重跑全套。默认golden只压缩排版，保留每个独立用例及全部预期字节。真实阶段receipt、设备断连/取消/清理及支持矩阵仍待设备验收，本次不运行。

Android/iOS业务App、BT/ISP/Wi-Fi固件、lt-vad/schema/rpc不受影响，原因是其实现和通信契约不在本方向修改范围。

</details>

## 4. 资源与交付计划

| 模块 | 执行 | 分支 | 首次交付 | 依赖 | 人日/版本/提测时间 |
|---|---|---|---|---|---|
| 契约与兼容回归 | 独立GPT6.1Sol进程B；人工负责人待确认 | codex/interface-capabilities | B0已提交 `eda742d` | 当前v0.5.0行为 | 人日/版本/提测待确认 |
| Python结构化错误/support（B1） | 同一进程B | codex/interface-capabilities | 实现与产品接线完成，设备未验证；2026-11-02核对 | B0；父会话review/提交/PR/CI | 人日/版本/提测待确认 |

B0 golden从共同base `b3c1a63` 的Python main通过fake run捕获，不含设备数据。B1默认输出和成功schema不改，未知异常阶段保持unknown；support不查询设备或声称available/verified。zsh早期错误和外部异常终止不承诺JSON。完整CI原生产物和设备矩阵需分别报告，临时安装中使用fake原生helper的主机回归不代替它们。
