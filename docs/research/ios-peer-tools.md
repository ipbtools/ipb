# iOS「类 adb」设备控制工具现状（2025–2026）调研

## 1. Facebook/Meta `idb`（fbidb）
- **架构**：`idb_companion`（macOS 上跑的 Objective-C++ gRPC server）+ Python 客户端；companion 封装了 `FBSimulatorControl`（模拟器）与 `FBDeviceControl`（真机）两套后端。MIT 协议。仓库仍有提交活动，README 提到正在向纯 Swift 迁移。（[GitHub](https://github.com/facebook/idb)、[commands 文档](https://fbidb.io/docs/commands/)）
- **真机 vs 模拟器的关键差异（重点）**：`ui tap` / `ui swipe` / 按键等 interact 类命令**在真机上不工作**，报错提示 target 不满足 `FBSimulatorLifecycleCommands` 协议——这套协议本身就是给模拟器设计的。真机侧的 `list-apps`/install/launch/文件操作基本可用，但 screenshot 在真机上历史上也有过多个反馈问题。（[idb issue #836](https://github.com/facebook/idb/issues/836)、[issue #531](https://github.com/facebook/idb/issues/531)）
- **HID 注入方式**：模拟器侧用的是 Apple 私有的 Indigo/SimulatorKit HID 注入通道（CoreSimulator 内建），这也是 `martingeidobler/ios-mcp-server` 明确说自己用 "native touch injection (IndigoHID)" 的同一机制——**仅限模拟器**。真机没有等价的公开注入通道，idb 对真机的 XCTest 执行支持有讨论但触控注入未落地。

## 2. `pymobiledevice3`（doronz88）
- iOS 17+ 起 Apple 把开发者服务迁到 CoreDevice/RemoteXPC，需要建立 RSD 隧道。默认情况下**无需 root**：macOS 上用系统自带 `remoted`/`remotepairingd`；Linux/Windows 用纯 Python 网络栈 PyTCP 在进程内建用户态隧道（该隧道只在本进程内可达，其他进程无法复用）。17.0–17.3.1 早期版本缺 CoreDeviceProxy，仍需 `sudo tunneld`。（[iOS17+ tunnels 指南](https://doronz88.github.io/pymobiledevice3/guides/ios17-tunnels/)）
- 文档提到支持"host-initiated developer services"和"device-initiated AV/HID paths"（视频/音频流+手势命令），但公开资料未详细展开 `developer dvt` 下 screenshot/simulate-location/accessibility-audit 等具体子命令行为。是目前对 iOS 17+ 支持最活跃、最主流的跨平台库，`tidevice3`、`go-ios` 生态都在向它靠拢或复用其协议实现。

## 3. `go-ios`（danielpaulus）
- MIT，活跃维护（主分支 711 commits，48 open issues）。支持 DDI 自动下载挂载（`image auto`）、iOS17+ 隧道（`sudo ios tunnel start`）、screenshot、装/卸/launch app、crash 管理、`runtest`（跑 XCUITest bundle）、`runwda`（启动 WebDriverAgent）。
- **对输入注入的立场很明确**：go-ios 自己不直接实现 tap/swipe，而是通过 `ui` 命令族把手势操作**委托给 WebDriverAgent 或 DeviceKit**。也就是说它是"把 WDA 管起来"的编排层，不是独立注入器。被 HeadSpin、Sauce Labs 用于生产。（[GitHub](https://github.com/danielpaulus/go-ios)）

## 4. `libimobiledevice` 系 / `tidevice` / `ios-deploy`
- `libimobiledevice` 1.4.0、`usbmuxd` 1.1.1 仍在维护（usbmuxd 2025-12 有提交）；`ideviceinstaller` 1.2.0 于 2025-10-30 发布，命令行改为 `install`/`list` 子命令风格。（[libimobiledevice news](https://libimobiledevice.org/news/2025/10/30/ideviceinstaller-1.2.0-release/)）
- 阿里 `tidevice`：原作者已明确**放弃在 tidevice 里自研 iOS 17 实现**，转而依赖 pymobiledevice3；其继任者 `tidevice3`（codeskyblue，pymobiledevice3 的易用封装）已于 **2025-07-30 归档**，官方建议直接用 pymobiledevice3。（[tidevice3](https://github.com/codeskyblue/tidevice3)）
- `ios-deploy` 仍是轻量装包/启动工具，无自研输入注入能力。

## 5. WebDriverAgent（appium fork）与真机触控原理
- WDA 通过链接 `XCTest.framework`，用 Apple 私有 API 在设备上执行命令；appium-xcuitest-driver 用 `devicectl`（iOS17+/Xcode15+）或 `appium-ios-device`（iOS16 及以下）来安装/拉起已预装的 WDA，减少每次 `xcodebuild` 启动开销。Sauce Labs 从 2026-01 起真机会话默认改用官方 Appium WDA，放弃了自维护的 SauceWebDriverAgent fork。（[Appium 文档](https://appium.github.io/appium-xcuitest-driver/latest/guides/run-preinstalled-wda/)、[Sauce Labs](https://docs.saucelabs.com/mobile-apps/automated-testing/appium/real-devices/)）
- **底层链路**（公开逆向资料佐证）：硬件事件 → IOKit 生成 `IOHIDEvent` → 经 Mach port 送到 SpringBoard → SpringBoard 分发给目标 App 主线程 runloop 的 source0 回调 → 封装成 `UIEvent`。XCTest/WDA 的 `XCUICoordinate.tap()` 等 API 正是通过系统私有接口合成这类 HID/UIEvent 注入到目标进程，**这套合成注入能力仅对已签名、挂载了 XCTest 的测试进程开放**，不存在系统级、任意进程可用的"adb input tap"等价物。

## 6. `xcrun devicectl` 与 Apple 官方 Xcode 27 "Device Hub"
- `devicectl` 目前**没有独立的 screenshot 子命令**（只能拿到 `screenViewingURL` 之类的元信息），也**没有公开的输入注入接口**；它是 Device Hub 的命令行对应物，主要用于 CI 流水线里装包/拉起而非交互控制。
- Xcode 27 的 Device Hub 把模拟器与真机管理界面合并，提供真机远程屏幕镜像/控制、系统更新触发等能力，但**社区反馈的重要限制**：屏幕镜像仅支持 iOS 27+ 真机（旧系统版本不支持）；不支持拖拽文件到模拟器（相对旧版是倒退）；缺少精确像素缩放和 Debug 菜单。目前没有公开的 CoreDevice `UniversalHID`/`dtuhidd` 逆向文档——这部分协议仍是黑盒，社区搜索未发现相关逆向成果。（[The Swift Dev](https://www.theswift.dev/posts/debug-ios-device-bugs-with-xcode-27-device-hub/)、[mjtsai 博客标题确认](https://mjtsai.com/blog/2026/06/25/xcode-27s-device-hub/)）

### 6.1 Device Hub 的快捷键约定（2026-09-08 实测，Xcode 27 beta 6 + iPhone 13 Pro）

我们做 `ipb mirror` 时需要一套键位约定。与其自创，不如照抄 Apple 自己的。
用 Accessibility API（`AXMenuItemCmdChar` / `AXMenuItemCmdModifiers`）读 DeviceHub 运行时的真实菜单：

| 功能 | 键位 | 备注 |
| --- | --- | --- |
| Home | ⇧⌘H | |
| App Switcher | ⌃⇧⌘H | |
| Siri | ⇧⌥⌘H | Home/Siri/AppSwitcher 共用 H，靠修饰键区分 |
| Lock | ⌘L | |
| 音量 + / − | ⌘↑ / ⌘↓ | 与 scrcpy 的 `MOD+Up/Down` 一致 |
| 截图 | ⇧⌘S | |
| 录屏 | ⇧⌘R | |
| 键盘捕获 / 软键盘 | ⌘K / ⌥⌘K | |
| 缩放适应 / 实际大小 | ⌘0 / ⌘1 | 另有 ⌘+ / ⌘− 缩放 |

对照 scrcpy 4.1（其 `--shortcut-mod` 默认 `lalt,lsuper`，macOS 上 Super 即 ⌘）：
Home = `MOD+h`、App Switcher = `MOD+s`、音量 = `MOD+Up/Down`、BACK = `MOD+b`／右键。
**音量三家一致；Home 的字母一致但 DeviceHub 多一个 Shift；App Switcher 两家完全不同。**
iOS 没有 BACK 键，scrcpy 的 `MOD+b`／右键没有直接等价物。

`ipb mirror` 选择对齐 DeviceHub，因为它是设备原厂语义，用户的肌肉记忆更可能在那边。

**取证线索：**DeviceKit.framework 里存在菜单标识符
`com.apple.devicekit.menu.controls.hardwareGestureControls.actionButton` 和 `.sideButton`，
但连 iPhone 13 Pro 时这两项不出现在菜单里（框架内有 `ConditionalKeyboardShortcut`，按设备条件显示）。
这既证实 13 Pro 没有 Action Button，也说明**换一台 15 Pro 连 DeviceHub 就能观察到它的实现**，
是后续为 Action Button 取 usage code 的可行路径。

## 7. iPhone Mirroring（macOS 15+）与商业设备云
- **iPhone Mirroring 官方无自动化 API**（Apple DTS 明确答复无此 API）；社区方案（如 midscene-ios、"iPhone Mirroir" MCP）本质是**截图 + 坐标映射到 Mac 屏幕再模拟鼠标点击**，即操作的是 macOS 侧的镜像窗口而非设备本身的注入通道。
- Sauce Labs / BrowserStack / AWS Device Farm 真机云的输入注入路径统一：**Appium → XCUITest driver → WebDriverAgent → XCTest**，或直接跑开发者自己的 XCTest UI bundle；AWS Device Farm 用 Amazon 托管的 macOS host 动态连接真机跑这套链路，没有绕开 XCTest 的旁路方案。（[AWS 文档](https://docs.aws.amazon.com/devicefarm/latest/developerguide/test-types-ios-xctest-ui.html)、[BrowserStack](https://www.browserstack.com/guide/appium-ios-tutorial)）

## 8. `Git-Agni/prod-FARM-IOS-Core`：一个 2026 年的真机农场，仍然只能走 WDA（2026-09-14 阅读）

[仓库](https://github.com/Git-Agni/prod-FARM-IOS-Core)。Apache-2.0，`@git-agni/phone-farm-core` 0.1.0-review.0，Node ≥22。
**本节依据 README + `docs/architecture.md` + `docs/coordinates.md` + `package.json`，未读源码**；凡涉及实现细节的判断都以这四份文档的原文为准。

开源的 iOS 真机农场，用途是在 9 台 iPhone 上跑 TikTok 自动化（README 引用的工程说明：
"TikTok on 9 real iPhones reverse engineered from the screen up…pixel-level UI detection,
OCR account switching, never posting twice"）。TypeScript/Node + PostgreSQL + Drizzle ORM。

四个常驻进程围绕 PostgreSQL：`web`（Fastify + HTMX 面板、JSON API、代理视频流）、
`worker`（消费 pg-boss 队列，每台设备一条 `ios-device-<hash(udid)>`，5 秒物化一次到期任务）、
`wda-service`（常驻 supervisor，每设备一个 WDA 实例，USB 转发控制口 8100+、视频口 9100+）、
`appium`（Appium 3 + XCUITest driver，只绑 loopback）。任务抽象成
`pluginId` / `taskType` / `taskVersion` + JSON payload 以保证向后兼容。

### 为什么它对本文档有价值

它是本文结论的一个**当前、真实、生产规模**的佐证样本：一个认真做农场的人，在 2026 年仍然
只能把控制权交给 Xcode 工具链。其架构文档写得很直接：

> "The farm never talks to a device directly at the USB level for *control*" —— 委托 Xcode 是强制的

具体链路：设备物理配对 + Developer Mode（iOS 16+），Xcode 首次配对时挂载 DDI，
`xcodebuild build-for-testing` 自动签名（UDID 烧进 provisioning profile），
再对每台设备 `xcodebuild test-without-building` 把 WebDriverAgentRunner 作为 UI test 装上并拉起。

由此带来的运维约束，都写在它自己的 "Key Constraints" 里：
**Apple ID 的免费 provisioning 有 100 个 UDID 上限**；**登录钥匙串必须在图形会话里解锁**才能签名；
非 loopback 绑定必须配 auth provider；任务有 30 分钟 run-window，过期即放弃。

### 与 ipb 的对照

| | prod-FARM-IOS-Core | ipb |
|---|---|---|
| 控制通道 | WDA（XCTest UI test）经 HTTP | CoreDevice/RemoteXPC → DDI 的 `dtuhidd` |
| 设备端进程 | 要装 WebDriverAgentRunner | 不装任何东西 |
| 签名 / Apple ID / provisioning | 全部需要，受 100 UDID 上限 | 全部不需要 |
| 每加一台设备的成本 | 烧 profile + `xcodebuild` 起一次 WDA | 开一个 service socket |
| 坐标模型 | 每种屏幕几何一套**编译进源码**的 points 常量表 | CLI 边界归一化 0..1 |
| 输入原语 | tap / swipe | tap/swipe/long/scroll(含完整 phase 序列)/key/button/digitizer |
| 画面 | MJPEG，浏览器可看（跨机器） | 本机 AppKit 窗口（`ipb mirror`），跨机器看不了 |
| 编排层 | 调度、插件、面板、多设备并发 | 无 |

### 坐标：它的做法比我们差，反过来印证了 Rule 2

> "A profile is a full set of tap targets for one screen geometry, in **points** (not pixels)"
> …… "not at runtime. A coordinate profile is a compiled constant in the source."

每种屏幕几何一套编译期常量表，靠人肉从截图读中心点、再发测试 tap 校验；**目前只 ship 了
iPhone 8（375×667）**，加 iPhone 13/14 要改两处源码再重新部署；另给 15 个单点 tap 目标留了
运行时覆盖入口（设备页 → Touch points）。

AGENTS.md Rule 2 的 "Coordinates are normalised (0..1) at the CLI boundary; nothing downstream
sees pixels" 在这个对照下是明显更优的选择：换机型不需要改代码。

### 值得借鉴的三点

1. **注册向导**：`src/devices/registration.ts` 逐步探测每个环节并针对失败给出具体修复动作 ——
   与 `ipb doctor` 同构，但它做进了产品流程。
2. **插件/任务版本化**：`pluginId` / `taskType` / `taskVersion` + JSON payload，是 agent 时代
   编排层的一个可抄的形状（见 `agent-frameworks.md`）。
3. **面板远程控制绕过 Appium**：`POST …/remote/action` 直接打 WDA 的 HTTP，说明作者自己也嫌
   Appium 那层慢 —— 交互路径和批量自动化路径分开，是个合理的结构决定。

其调度、账号切换、OCR 等领域逻辑与本项目目标无关，不具复用价值。

### 共同的空洞：都没有 UI 层级

它用"编译坐标表 + 像素级检测 + OCR"应付"按钮在哪"；ipb 的能力矩阵里 UI hierarchy 直接是 no。
它的答案很脆（只覆盖一种机型），但至少是个答案。**这条路线不能照抄**，然而 ipb 若要往 agent
方向走，这个问题躲不掉。

## 对比表

| 工具 | 真机支持 | 需要设备端 App/Server | 需要 XCTest | 需要 Mac | 输入注入方式 | 截图方式 | License | 活跃度(截至2026-09) |
|---|---|---|---|---|---|---|---|---|
| idb | 部分（无 tap/swipe） | idb_companion(Mac) | 仅部分真机流程 | 是 | 模拟器=Indigo HID；真机=不支持 | 模拟器完善，真机历史多 bug | MIT | 有提交，架构迁移中 |
| pymobiledevice3 | 是 | 否（RSD隧道） | 否（多数功能） | 否（跨平台） | 未见公开真机通用注入API | developer dvt 截图 | MIT | 最活跃，2026仍在更新 |
| go-ios | 是 | 依赖DDI/隧道 | 委托给WDA | 否（Go跨平台） | 委托WDA/DeviceKit，自身不做 | 支持 | MIT | 活跃，产业采用(Sauce/HeadSpin) |
| libimobiledevice/ideviceinstaller | 是(装包为主) | 否 | 否 | 否 | 无 | 无 | LGPL | 活跃(2025-10发布) |
| tidevice/tidevice3 | 是 | 否 | 部分 | 否 | 依赖WDA | 支持 | MIT | tidevice3已归档(2025-07) |
| WebDriverAgent | 是 | 是(WDA需装到机器上) | 是 | 是(构建/签名) | XCTest合成HID/UIEvent | 支持 | Apache2.0 | 活跃(appium维护) |
| xcrun devicectl | 是 | 否 | 否 | 是 | 无 | 无独立命令 | Apple专有 | 随Xcode更新 |
| Xcode 27 Device Hub | 是(iOS27+镜像) | 否 | 否 | 是 | 官方黑盒(未逆向) | 屏幕镜像 | Apple专有 | 2026新功能 |
| iPhone Mirroring+社区自动化 | 是 | 否(系统内建) | 否 | 是 | 截图+坐标映射点击Mac窗口 | 系统镜像 | Apple专有+MIT封装 | 活跃(社区MCP) |
| Sauce/BrowserStack/AWS Device Farm | 是 | 是(WDA/XCTest bundle) | 是 | 云端Mac host | XCTest/WDA | 支持 | 商业 | 活跃 |
| prod-FARM-IOS-Core (农场) | 是 | 是(WDA) | 是 | 是(签名+xcodebuild) | WDA HTTP → XCTest | WDA 截图 / MJPEG 流 | Apache2.0 | 2026-09 公开，0.1.0-review.0 |

## 结论：真机上没有任何开源工具能在不装设备端 server 的前提下提供的能力
截至目前公开资料，**在物理 iOS 设备、且不预先安装/签名任何设备端进程（无 XCTest bundle、无 WDA、无镜像 App）的前提下，没有开源工具能提供系统级任意坐标的触控/按键注入**（等价于 adb 的 `input tap`）。原因是 Apple 把 `IOHIDEvent` 合成注入能力锁定在经开发者证书签名并挂载 `XCTest.framework`/`testmanagerd` 的进程里；pymobiledevice3、go-ios 提供的都是隧道/协议层（RSD、DDI、devicectl 通道），真正落地的触控注入最终都要绕回 WebDriverAgent/XCTest 这条唯一公开路径。同样，Device Hub 背后的 `UniversalHID`/`dtuhidd` 协议目前仍是 Apple 内部黑盒，没有公开逆向实现可用；iPhone Mirroring 的自动化方案本质是"操作 Mac 窗口"而非"注入设备"。因此，"不依赖设备端 server 的真机 adb 等价物"在当前生态里**不存在**。

2026-09-14 补充佐证：`prod-FARM-IOS-Core`（第 8 节）是一个 2026 年公开的生产级真机农场，仍然
走 WDA/XCTest，并为此付出签名、provisioning、100 UDID 上限、钥匙串解锁这一整套代价。它没有
推翻上面的结论，而是再次确认了它 —— 同时也说明 ipb 走的 `dtuhidd` 路线到目前为止仍无第二个
公开实现。

（因搜索工具限制，`mjtsai.com` 原文被 403 拒绝，仅取到标题与搜索摘要；如需更深入的 Device Hub 技术细节，需要访问 Apple 官方 Xcode 27 release notes 或后续逆向文章。）
