# MCP 与 agent 体验优化

> 状态：M1已接入CLI/安装/主机检查；设备验收待完成；最后核对：2026-11-02。执行进程：GPT6.1Sol / xhigh / Fast(priority)，方向A。

## 1. 需求与关联资料

用户在2026-10-27授权：与Opus5.5讨论后，设立两个大方向，各由独立GPT6.1Sol/xhigh/Fast进程跟进。基线为main `bf3fcad375db5e11d5573a7ef11fa9a02c8cd1d7` / v0.5.0。产品继续只使用Apple自带服务；不安装手机Runner、不启动XCTest，不把过去版本的实机豁免继承为本次验收。用户在2026-11-02进一步授权落地并提PR；本轮完成首期产品接线和主机回归，实机项保持未验证，不自动合入或发布。

ipb已有完整native deep读取和受保护的单步操作，但agent仍需拼接CLI、处理输出和协调设备。目标是让agent通过小而明确的工具集获得新鲜页面、执行一次操作并理解结果。

- 既有后端与限制：[UI指南](ui.md)、[无Runner元素方案](runner-free-elements.md)。
- 权威接口契约及方向B：[接口能力与规范补充](interface-capabilities.md)。
- 参考：[iPhone-use MCP](https://github.com/zhongerxin/iPhone-use/blob/3ce9c080534e89fab91a237bf1c53a4a7e9d80a7/server/iphone_use.py)、[agent-device会话生命周期](https://github.com/callstack/agent-device/blob/5b61e8a9ad3d16d34c4462ca6749937571b54c88/docs/adr/0014-session-ref-frame-lifetime.md)、[ios-use diff](https://github.com/xhzq233/ios-use/blob/bf92d63df6e43c4348c290b57f6132562ec4a934/README.md#L364-L391)。借鉴设计，不引入其XCTest执行层。
- Figma、App/固件需求及跨仓schema/rpc：不涉及；本次新增功能在Mac主机。

## 2. 技术调研结论

首期采用薄stdio MCP进程，每次操作调用当前安装的ipb CLI，不直接import或复制AX后端。先交付新鲜观察、精确操作、机器可读结果和MCP间的设备互斥，再做diff、settle及跨页收集。MCP运行时与常驻DTX连接是不同能力，首期不复用DTX或缓存native handle。

`Sources/ipb_mcp_adapter.py`集中定义有界工具schema、argv构造、v0.5.0按命令族的保守映射和v1错误样例消费。observe保留原生路径/字段，返回独立MCP envelope；底层schema1/2不变。当前开发和验证只使用主机fake数据，真实设备路径均待验收。2026-11-02重新核对六个参考仓库的默认分支；iPhone-use未变，其余更新没有改变本期无Runner方案。go-ios的[截图串行/取消边界](https://github.com/danielpaulus/go-ios/blob/51887da850dd19f4242c58a00262d06e006839cf/ios/screencapture/screencapture.go#L33-L47)与agent-device的[操作证据边界](https://github.com/callstack/agent-device/blob/32bf98def5e3b0c6d577ed96ac09309d4e7353f0/packages/apple-runner/src/runner-failure-diagnostics.ts#L23-L50)作为设计参考，不复制执行层或新增连接管理。

M1正式入口为`ipb mcp`（开发也可直接运行`python3 Sources/ipb_mcp.py --cli /absolute/path/to/ipb`），使用MCP revision 2025-11-25的有界stdio子集；工具和结果指南见[docs/mcp.md](mcp.md)。`Sources/ipb_mcp_process.py`拥有锁、持久化intent及取消回收；没有引入SDK/AX依赖，由父会话接通同一安装的CLI、三个Python模块及主机/包检查。后续M2–M4未实现。

<details><summary>选择与约束</summary>

- 首期可以用标准库实现有界且经过协议测试的stdio JSON-RPC/MCP子集，明确支持的协议版本和方法。不得扩大成自行重写整套MCP框架；若需要SDK，必须使用独立依赖文件并单独说明原因，不能改变固定AX依赖。
- 设备操作只接受完整CoreDevice UUID；操作参数用argv传递，不通过shell拼接。既有CLI仍保留名称/前缀选择方式。
- 每次observe获取新鲜native deep快照；紧凑输出不制造XCTest类型、hittable或缺失属性。`n…`仅本次输出有效，不能作为后续action token。
- 未确认的结果、取消、提交后失败不自动重放。页面稳定与业务成功分别报告。
- 拒绝方案：同时重写传输和MCP；用位置编号跨快照操作；失败后隐式切坐标/OCR。

</details>

## 3. 技术方案总括

A拥有 `Sources/ipb_mcp.py`（及必要的同前缀模块）、`scripts/test_mcp.py`（及同前缀维护测试）和 `docs/mcp.md`、本方案。`Sources/ipb_ax.py`、`bin/ipb`与权威契约由B拥有；Makefile、主机检查入口、workflows、打包/安装、README、文档目录、completions、VERSION由父会话统一接线。A提交建议patch或接线清单，不修改父会话文件。

MVP工具范围：设备枚举、observe、locate、wait、press、input、scroll_to_visible、alert_press，以及明确目标的Home/launch/tap/swipe。不能安全映射结果的工具必须收缩或明确不可用，不能推测成功。裸text暂不暴露；其剪贴板/粘贴阶段由B补齐后再讨论。

<details><summary>接口、生命周期与交付边界</summary>


### 已冻结的最小错误对象

共享示例为[docs/contracts/ipb-error-v1.example.json](contracts/ipb-error-v1.example.json)，是待实现的v1契约样例，不是既有产品输出或设备证据。结构固定为kind=ipb.error、contractVersion=1、operation、phase、exitCode、error(type/message)、action、retrySafe、result。

- 枚举未知时明确unknown；读操作action=null，无可保留结果时result=null。动作细节保留not-sent/submitted/accepted/refused、child-exited-zero/nonzero、native-true/false等原生信息，不把它们混成业务成功。
- 非零退出时stdout最多一个ipb.error JSON；保留的完整native结果置于result，原始schema不改。退出0仍原schema1/2。首期结构化错误以Python路径为边界；zsh早期错误可能没有JSON，消费者必须保守兼容。
- retrySafe只表示此操作是否可安全重试；仅只读或可证明not-sent可以true。不能以此自动跳过新的目标/前提校验。signal、returncode<0、>=128、应为JSON却解析失败或信息不足都按unknown。
- A只在kind与contractVersion均匹配时消费v1；转换仍集中于一个适配模块。B维护正式docs/contract.md及契约fixture。

### 共享结果与兼容

所有退出码/状态按B契约解释，转换集中在单一适配模块。初期可独立测试v0.5.0既有stdout和按命令族的退出码；非零退出时也检查stdout是否仍有完整native结果。外部终止、异常退出、信息不足时按unknown处理，不从stderr自由文本猜测未发送。方向B提供opt-in错误对象后只替换该模块；缺失时保守处理。

### 设备互斥与取消

- 请求内按UUID异步互斥并获取跨MCP进程的flock；锁FD由server持有，不传给CLI。读写设备请求均受互斥。首期不保护直接手工CLI或mirror；统一CLI重入锁列为后续，不能假称已覆盖。
- 子进程使用独立进程组。`ui input`内的text又有独立session，父CLI退出不等于全部回收。必须测试“外壳先退出、孙进程继续持有pipe”和独立session嵌套情形。
- 对取消的清理给予覆盖真实后端清理预算的有界grace；当前源码的关闭阶段上界合计18.5秒，另含调度/IO开销；只发一次SIGTERM，不能重复取消打断finally，不把单个固定等待值当终止证明。只处理本请求拥有的进程。
- 强杀后无法证明子进程回收时记unknown/orphanPossible，并持久化隔离该设备的后续修改。隔离不能因60秒到期、一次observe或server重启自行解除；恢复必须有明确终止证据或人工介入。
- 只有“结果未知但确认进程全部回收”的情况可以通过一次成功、完整且匹配设备的观察解除observeRequired。无完整snapshotId的超时观察不能解除。

M1作保守收窄：`orphanPossible`阻止该设备所有MCP请求，包括observe，避免未知残留期间再建立AX连接；只允许`observeRequired`用完整observe解除。进程身份预检失败时不启动CLI；运行中检查失败或强杀时保留`orphanPossible`。真实Darwin ps/sysctl权限与行为仍待主机验收；当前sandbox禁止`/bin/ps`，维护测试注入协作fake CLI的进程身份，不能替代该验收。

旧AX错误缺少receipt时，MCP不再单凭1/5认定not-sent；只有结构化已知状态、可证明未spawn或HID族明确的准备阶段映射才表明未发送。读取方向B已提交契约后，dump采用`operation=ui.dump`；child负值/≥128保留数值且状态unknown。此保守映射需父会话接线时复核，不改默认CLI输出或退出码。

维护fixture确认的可达主机问题：CLI的waitpid完成与pipe EOF可能相差一次调度；若即时把未读到EOF归类为孙进程残留，普通成功观察会被误判。实现先给予150ms有界尾部排空，再判定持续残留；外壳先退出且独立session孙进程仍持有pipe或已关闭pipe的场景仍触发回收/隔离。

源码确认的旧CLI兼容边界：`bin/ipb`的query_ui按文本精确匹配枚举identifier。MCP仅规范化锁键，传入CLI的完整UUID保留调用者观察到的大小写；相同UUID的大小写变体仍共用锁，避免MCP自行小写化导致正常大写枚举UUID被旧CLI拒绝。

持久化操作intent必须在spawn前落盘，随后补齐本请求pid/pgid/启动时间及唯一环境标记。server崩溃也要留下可判定或保守隔离的记录；不能只靠flock自动释放。不得把人工解除隔离暴露成MCP工具。进程标记检查只提取本请求nonce/身份，不输出或保存完整环境、argv和用户输入。共享同一canonical锁路径的其他checkout也受保护，使用不同状态目录的进程不受保护。

MCP首期固定一个实际测试的协议revision，覆盖initialize、notifications/initialized、ping、tools/list、tools/call、notifications/cancelled。不支持的请求返回-32601；通知不发JSON-RPC响应。stdout仅NDJSON，日志放stderr，资源与参数有界。

### 里程碑

M1：已落源码与主机fixtures，协议握手/工具schema、薄CLI适配、紧凑observe、锁、失败/取消边界均有对应模块；真实主机/设备验收和父会话接线待处理。M2：保守语义diff和可选动作后观察/有限settle。M3：有预算的scroll-find/collect，页级来源、去重限制、结束证据和no-progress分开。M4：仅在实测瓶颈明确后设计连接复用。本轮未扩大到M2–M4。

### 验证

主机fixture覆盖握手/非法请求/参数边界、默认输出解析、same-device串行/different-device并行、跨server互斥、异常退出、进程树清理、隔离/observeRequired。fake CLI不得访问真实设备或剪贴板。实机待验包括真实press/input/alert取消、观察延迟、设备断连；CI/fixture不能替代它们。

其他Looktech App、BT/ISP/Wi-Fi固件、lt-vad/schema/rpc不受影响：本方向不修改其代码或协议。

</details>

## 4. 资源与交付计划

| 模块 | 执行 | 分支 | 首次交付 | 依赖 | 人日/版本/提测时间 |
|---|---|---|---|---|---|
| MCP与结果适配 | 独立GPT6.1Sol进程A；人工负责人待确认 | codex/mcp-agent-experience | 可评审的实现提交、维护测试、docs/mcp.md和接线清单 | 冻结的B契约词汇；首期不等待B代码 | 待确认 |
| diff/settle/list后续 | 同一进程持续跟进 | 同分支分阶段提交 | M1完成后另定增量 | M1结果/取消边界 | 待确认 |

M1为已实现未验证状态；主机fixture不构成设备验收。不得自动发布、合入或升级默认本机安装。代码及文档仅在方向A工作树内；本地提交如受执行环境限制，阻塞和实际提交清单保留在本地STATUS/交接中，不用不存在的SHA声称完成。

首期主机联调确认两项问题并作最小修正：`tools/list`原先拒绝合法通用`_meta`，现校验其为对象后忽略；Darwin `KERN_PROCARGS2`可能在进程退出后返回EINVAL，原先会把这个竞态判为权限缺失。现在只在再次读取进程身份确认该PID消失/身份变化时忽略读取失败；仍存活且不可读时继续在发送前失败。真实主机回归使用假CLI验证正常退出、取消独立session子进程及外壳先退场景，不代表手机清理通过。
