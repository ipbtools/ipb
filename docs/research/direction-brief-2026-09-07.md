# devicehubctl 演进方向评审 brief（2026-09-07）

## 目标（用户原话）
"做成一个类似 adb 的工具，能让 iOS 设备像 Android 一样方便地、不依赖任何 XCTest 和手机上 server 的方式操控手机，方便后续的 agent 时代操控。"

## 当前已验证的事实（本会话实测，非推测）
1. Apple 自己的 iOS DDI（Xcode 27 beta，CoreDevice 642.x）里有 `/usr/libexec/dtuhidd`，以 RemoteXPC 服务 `com.apple.coredevice.hid.universalhidservice` / `hid.indigo` / `hid.universalhid` 提供触摸、键盘、按键、滚动注入。这是 Xcode 27 Device Hub 的底层。**不需要 XCTest、不需要在手机上装任何第三方 server**，DDI 是 Apple 签名的系统组件，iOS 27 设备会自己以 MobileAsset 拉取。
2. 线上格式是普通 XPC 字典（已抓包，见 docs/protocol.md）：`{messageType:"Request", featureIdentifier, payload:{send:{_0:<HID 报文字节>, _1:serviceID}}}`，Indigo 事件是 `IndigoButtonEvent/IndigoDigitizerEvent/IndigoScrollEvent` 几个字段，barrier 是 `{isBarrier:true}` 同步。无 Mercury 类型包装。
3. 两条主机路径都已实测通过（iOS 27.0 24A5430a，iPhone 12 mini 与 13 Pro）：
   - A. 现有 helper（ObjC + 手写 Swift ABI shim，链接 CoreDevice 私有框架）在 macOS 27 b8 和 macOS 26.5.1（装了 Xcode 27 b6）上 39 步交互冒烟全过；tap 打开日历，recents 出 App Switcher。
   - C. pymobiledevice3 11.8 用户态隧道（无 root、无 CoreDevice）直连 dtuhidd：`connectedServices` 返回 5 个服务，两条原始 `send` 字典完成真实点击；DVT 截图 2.2 s；accessibility `list-items` 只给 caption 无坐标；barrier 回复超时（未解）。
4. 同一 DDI 还提供（RemoteXPC，已列举）：dtscreencaptured 截图、dtremotedisplayd 视频/音频流（startvideooutput/startmediastream）、dtpasteboardd 剪贴板、dtlocationd 模拟定位、dtappserviced 安装/启动/进程列表/信号/spawn、dtfileserviced 文件、dtdeviceinfod 设备信息/锁屏状态/显示信息、dthidd 方向、dtconfigurationd 外观/VoiceOver/配置文件、dtdebugproxyd debugserver、dtdiagnosticsd sysdiagnose、reboot。即 adb 大部分动词在设备侧已有 Apple 官方服务。
5. 主机侧要求：设备已配对信任；CoreDevice tunnel 已 connected（否则错误 4000）；用 CoreDevice UUID。设备侧要求：DDI 已挂载（iOS 27 自取；iOS 26 设备 + Xcode 27 DDI 未测）。
6. 生态对照（三份调研摘要在同目录 research/adb.md、agents.md、peers.md）：
   - 所有严肃 iOS agent 方案（Maestro、Appium/WDA、agent-device、Arbigent 经 Maestro、mobile-mcp、设备云）最终都落到"设备上跑签名的 XCTest runner"，被吐槽为 macOS tax、WDA flaky、真机/模拟器不对等；idb 真机不能 tap；go-ios 把注入委托给 WDA；调研结论是"真机无 server 注入不存在、dtuhidd 是黑盒"。**本工具正好填这个缺口**，且目前没有公开竞品。
   - adb 的 agent 最小闭环：截图 + 带坐标 UI 树 + tap/text/key + 启动 app + 日志；scrcpy 用常驻 server + 长连接做 35~70 ms 的画面流和连续手势。
   - LLM 原生工具的形态趋势：MCP server 暴露 tap_on / inspect_view_hierarchy / take_screenshot / launch_app；accessibility-first、截图兜底。

## 当前代码形态与债
- 单次调用模型：每条命令新起进程、新建 socket、发完就断，700 ms 等待；无常驻连接，无法做连续手势/低延迟。
- helper 绑定约 110 个私有 Swift 符号（seed 升级即可能断），wrapper 是 zsh。
- 只有 macOS；分发需要 Apple 的 XcodeSystemResources.pkg + MobileDevice.pkg（不可再分发，需从 Xcode xip 提取）。
- 缺口：带坐标的 UI 树；Unicode 文本输入（HID 键盘 usage 只覆盖 ASCII 键位，剪贴板服务可作替代）；连续画面流未接；日志/安装/文件等 adb 动词未包装；无 MCP。

## 候选方向
- D1 macOS 原生 C/ObjC 工具，去掉 Swift ABI shim，直接用抓到的 XPC 字典 + CoreDevice 的 createservicesocket；常驻 daemon 持有 tunnel/socket，CLI 通过本地 socket 调用（adb server/adbd 的 host 侧翻版）。依赖 Apple 两个 pkg。
- D2 Python 客户端基于 pymobiledevice3（GPL-3.0）：跨平台（Linux/Windows 也能建用户态隧道）、DDI/DVT/隧道/截图/日志/安装现成，只需补 HID 字典层与 MCP；许可证与分发（pip）需评估。
- D3 自研（Go/Rust/C）RSD 隧道 + RemoteXPC + HID 字典，或基于 go-ios（MIT，已有隧道与 DDI）扩展；真正的单二进制 adb 等价物，工作量最大。
- D4 混合：先用 D2 做 agent 可用的 MVP（MCP + CLI），把协议与验收沉淀成规范，再决定是否 D3。

## 请评审的问题
Q1 方向选择与阶段划分（MVP 应该是什么、给谁用、多久）。
Q2 架构：是否必须做常驻 host daemon + 长连接才能满足 agent 的延迟/连续手势；截图/画面流走 dtscreencaptured/DVT 还是 dtremotedisplayd 视频流。
Q3 UI 树：在无 server 前提下获得带坐标的元素树有哪些可行路径（accessibility 服务更深协议、VoiceOver 服务、视觉模型兜底、混合）；agent 是否可以接受"截图 + 归一化坐标"为主。
Q4 文本输入：HID 键盘 vs 剪贴板服务 + 粘贴键 vs 两者。
Q5 风险与护栏：私有协议随 seed 漂移、`com.apple.private.CoreDevice.hid` 权限目前未被强制但可能收紧、DDI 来源/合规、iOS 26 设备支持、Apple 正式版行为变化；应建立怎样的兼容性矩阵与冒烟门禁。
Q6 许可证/分发：pymobiledevice3 GPL-3 对产品化的影响；Apple pkg 不可再分发的安装方案；Mac-free 的价值有多大。
Q7 你认为的优先级排序与前 4 周的具体里程碑。

输出：按 需拍板 / 可自助修 / 已否决（不再提） / 验证资源 四块，每条含 来源 / 归属层 / 根因已明或未明 / 影响，并给推荐路线与里程碑。中文。
