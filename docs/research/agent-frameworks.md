# AI 手机操作 Agent 框架现状调研（2025–2026）

## 一、整体格局

2024–2026 年间，"让 LLM 直接操作手机"从学术原型（AppAgent、Mobile-Agent、AutoDroid）演变为工程化产品：一类是**测试/自动化框架加装 MCP 接口**（Maestro、Appium、agent-device），另一类是**原生为 LLM 设计的手机操作层**（DroidRun/Mobilerun、mobile-use、mobile-mcp）。共同点是几乎都复用了成熟的移动测试基础设施（Android 的 Accessibility/UIAutomator/ADB，iOS 的 XCUITest/WebDriverAgent），而不是自己重新发明设备驱动层。

## 二、Arbigent（takahirom）

Arbigent 是 Kotlin 编写的开源 AI 测试框架，覆盖 Android、iOS、Web、TV，核心思路是把复杂任务拆解为多个有依赖关系的"场景（scenario）"，配合 UI 树优化、卡屏检测、AI 图像断言提升可靠性。它**不自己实现设备驱动**，而是通过集成 Maestro 的 YAML flow 作为初始化/前置步骤来复用 Maestro 的 Android/iOS driver；同时支持 MCP 以调用外部工具，可选 OpenAI/Gemini 等多个模型后端。也就是说 Arbigent 处于"编排层"，设备控制仍下沉给 Maestro（因此 iOS 侧最终还是走 XCUITest）。

来源：[GitHub - takahirom/arbigent](https://github.com/takahirom/arbigent)，[Medium 介绍文](https://medium.com/@takahirom/introducing-arbigent-an-ai-agent-testing-framework-for-modern-applications-f43a2e01d342)

## 三、Maestro（mobile-dev-inc）

Maestro 的 iOS driver 是其中最复杂的部分：Kotlin 端 `XCTestIOSDevice` 通过 `XCTestDriverClient` 与设备上安装的 Swift 编写的 **XCTest runner**（`maestro-driver-iosUITests.xctrunner`）通信，runner 在设备上起一个 HTTP server（早期端口 22087，新版本还涉及 7001 等端口），本质仍是基于 XCUITest 框架驱动 UI，与 WebDriverAgent 思路一致，只是自研而非依赖 Appium 生态。物理设备支持是后加的（社区贡献 `maestro-ios-device`/`maestro-runner` 项目专门补齐真机场景），仍反复出现如 "iOS driver not ready""XCUITest port unreachable" 等 Xcode 26/26.2 兼容性问题。2026 年 2 月起 Maestro 内置了 **MCP server**，暴露 `launch_app`、`tap_on`、`inspect_view_hierarchy`、`take_screenshot`、`run_flow` 等工具，可直接被 Claude Code、Cursor、Codex、Gemini、Windsurf 等 agent 调用，Android 侧可直接连物理设备，iOS 侧一般还是先起模拟器。

来源：[iOS Driver Architecture - DeepWiki](https://deepwiki.com/mobile-dev-inc/Maestro/4.1-ios-driver-architecture)，[maestro-ios-device](https://github.com/devicelab-dev/maestro-ios-device)，[Maestro MCP 介绍](https://maestro.dev/blog/maestro-mcp-an-introduction)，[Maestro MCP 文档](https://docs.maestro.dev/get-started/maestro-mcp)，[iOS driver 兼容性 issue](https://github.com/mobile-dev-inc/Maestro/issues/2932)

## 四、Apple 官方能力

Apple 自己没有对外提供"给 LLM 用"的自动化 API，仍然只有 **XCUITest/XCTest**（需要签名的测试目标、跑在设备/模拟器上）。Xcode 26/27 引入了 **CoreDevice** 框架和命令行工具 `xcrun devicectl`，可以 install/launch app、管理进程，Xcode 27 还推出新的 **Device Hub** App 取代旧版 Simulator.app，把物理设备和模拟器统一管理，devicectl 也扩展到能管理模拟器；但早期 beta 中不少 devicectl 的模拟器子命令仍不可用。CoreDevice/devicectl 定位是"设备管理与进程控制"，并不提供无障碍树快照、tap/swipe 坐标注入这类 UI 自动化原语——这些仍必须经由 XCTest。因此任何第三方 agent 想在 iOS 上做 UI 级操控，最终都绕不开"起一个签名的 XCTest/XCUITest runner 跑在设备上"这条路。

来源：[WWDC 2026: Device Hub 与 CI/CD - Bitrise](https://bitrise.io/blog/post/wwdc-2026-device-hub-and-what-it-means-for-ci-cd)，[Meet CoreDevice and devicectl](https://speakerdeck.com/scenee/meet-coredevice-and-devicectl)

## 五、Appium / WebDriverAgent 及 AI 适配

WebDriverAgent（WDA）本质是链接 `XCTest.framework`、实现 W3C WebDriver 协议的 HTTP server，被 Appium 用作 iOS/tvOS 的执行后端，需要用开发者证书签名后装到设备上跑。2025–2026 出现了面向 LLM 的适配层：**Appium MCP** 把 Appium 会话包装成 MCP 工具，让编码 agent"意图驱动"而非维护固定脚本；社区也有直接基于 Appium/WDA、以紧凑文本 UI 树 + testID 优先定位驱动真机 iPhone 的 LLM 原生 CLI。这条路线的通病是 WDA 的稳定性问题（端口未就绪、弹窗未被清理导致"假 flaky"）和证书/签名维护成本，被称为"macOS tax"。

来源：[appium/WebDriverAgent](https://github.com/appium/WebDriverAgent)，[Appium MCP 说明](https://medium.com/@kaushiksudhir/the-future-of-ios-test-automation-llm-and-mcp-integration-with-appium-2-x-561b585dd834)，[iOS CI 的 macOS tax](https://medium.com/@rnovokhatski/ios-automated-tests-in-ci-simulators-webdriveragent-and-the-macos-tax-39d5275836e3)

## 六、学术/研究类移动 agent 与基准

- **Mobile-Agent 系列（X-PLUG/阿里）**：从最初结合 OCR+图标检测的视觉 GUI agent，演进到 Mobile-Agent-v3/GUI-Owl（多模态跨平台 GUI VLM，具备感知、定位、端到端操作能力的多 agent 框架）。
- **AppAgent / AppAgent v2**：基于 GPT-4V，从 XML 中枚举 UI 元素后决策执行。
- **DroidBot-GPT / AutoDroid / AutoDroid-V2**：把 App GUI 状态转成自然语言 prompt 驱动 LLM，AutoDroid 结合动态 App 分析优化任务自动化，V2 用代码生成、面向小模型（SLM）。
- **基准**：AndroidWorld（116 个可编程任务、20 个真实 App，观测空间=全分辨率截图+无障碍 UI 树，动作空间=tap/swipe/type/home/back）；AndroidLab（138 任务、9 个 App，SoM 与纯 XML 两种模式，动作空间为 Tap/Swipe/Type/Long-Press+Home/Back）；MVISU-Bench、Mobile-Bench 等聚焦多 App/含糊指令/跨 App 场景。第三方评测中 **DroidRun** 在 65 项真实任务里以 43% 成功率领先 Mobile-Agent、AutoDroid、AppAgent。

来源：[X-PLUG/MobileAgent](https://github.com/X-PLUG/MobileAgent)，[Mobile-Agent-v3 论文](https://arxiv.org/pdf/2508.15144)，[AndroidWorld 论文](https://arxiv.org/html/2405.14573v4)，[AndroidLab 论文](https://arxiv.org/pdf/2410.24024)，[65 任务评测](https://aimultiple.com/mobile-ai-agent)

## 七、面向 LLM 原生设计的手机控制层

- **DroidRun/Mobilerun**：开源、LLM 无关框架，同时支持 Android 和 iOS，Android 侧通过配套的 **Mobilerun Portal** 无障碍服务 App 实时高亮/采集可点击、可编辑、可滚动元素；支持 CLI、TUI、Docker、Python API 调用 OpenAI/Anthropic/Gemini/xAI/Ollama 等模型。
- **mobile-mcp（mobile-next）**：MCP server，"accessibility-first"——优先用原生无障碍树而非截图坐标，退化时才用截图+坐标；统一暴露 tap/swipe/手势、App 安装/启动/终止、录屏、硬件按键、deep link、屏幕方向等能力，宣称 iOS/Android、模拟器/真机、Claude Code/Codex/Gemini 等客户端"零平台专属胶水代码"即可用。
- **agent-device（Callstack）**：CLI + MCP server + Node.js API，覆盖 iOS/Android/HarmonyOS/TV/Web/macOS/Linux，把 XCUITest、simctl、devicectl、ADB、UIAutomator、AT-SPI2 等平台专属工具统一抽象在一层 API 之下；iOS 侧直接调用 XCTest（而非 WebDriverAgent），有专门的坐标优先元素定位与稳定性 preflight 机制。
- **idb / idb-mcp（Facebook + 社区封装）**：idb 只支持 **iOS 模拟器**，因 iOS 安全模型限制无法在物理真机上做 UI 自动化；**pymobiledevice3** 纯 Python 实现，可在 Windows/Linux/macOS 上跨平台驱动 iDevice（设备发现、端口转发、日志、DDI/DVT 开发者工具等），但不做 UI 自动化，是"设备管理层"而非"UI 操作层"。

来源：[droidrun/mobilerun](https://github.com/droidrun/mobilerun)，[mobile-next/mobile-mcp](https://github.com/mobile-next/mobile-mcp)，[callstack/agent-device](https://github.com/callstack/agent-device)，[facebook/idb](https://github.com/facebook/idb)，[doronz88/pymobiledevice3](https://github.com/doronz88/pymobiledevice3)

## 八、大厂计算机使用（computer-use）在手机上的延伸

Anthropic 的 Computer Use 是"截图 + 鼠标/键盘"这种可移植的工具协议，跨 VM/容器/远程桌面，本身不绑定 OS；近期给 Claude Pro/Max 加入了"用手机远程操控电脑"的能力，但这不等于"直接操控手机 App"。Google 的 Gemini 2.5 Computer Use 源自 Project Mariner 的浏览器自动化研究，更偏重 DOM 感知，也覆盖 Firebase Testing Agent 等场景，在网页与移动端控制基准上有优势，但走的仍是"浏览器/DOM 优先"路线，不是无障碍树优先。两者目前都不是专门为原生 Android/iOS App 无障碍树设计的产品化方案。

来源：[Claude 手机远程操控电脑 - CIO Dive](https://www.ciodive.com/news/anthropic-claude-computer-access-AI/815730/)，[Gemini 2.5 Computer Use 发布](https://blog.google/innovation-and-ai/models-and-research/google-deepmind/gemini-computer-use-model/)

## 九、对比表：框架 → 平台 → iOS 控制层 → 是否需要设备端 server → 是否需要 XCTest → 许可证

| 框架 | 平台 | iOS 控制层 | 需要设备端 server/App | 需要 XCTest | 许可证 |
|---|---|---|---|---|---|
| Arbigent | Android/iOS/Web/TV | 委托 Maestro（XCUITest） | 是（Maestro runner） | 是 | Apache-2.0 |
| Maestro | Android/iOS | 自研 XCTest runner（HTTP server） | 是 | 是 | Apache-2.0 |
| Appium + WebDriverAgent | Android/iOS | WebDriverAgent（XCUITest） | 是（需签名安装） | 是 | Apache-2.0 |
| Appium MCP | Android/iOS | 同上，包一层 MCP | 是 | 是 | 视上游而定 |
| mobile-mcp | Android/iOS | 未公开自研细节，底层仍需平台自动化能力 | 视平台而定 | 真机场景通常需要 | Apache-2.0 |
| agent-device | Android/iOS/HarmonyOS/TV/Web/macOS/Linux | 直连 XCTest | 是 | 是 | MIT |
| DroidRun/Mobilerun | Android/iOS | 未详述 iOS 底层，Android 用无障碍服务 App | Android 需要 Portal App | iOS 场景通常仍需 | 开源（GitHub） |
| idb | iOS（仅模拟器） | XCTest（companion） | 是（macOS companion） | 是 | MIT |
| pymobiledevice3 | iOS（设备管理，非 UI 自动化） | DDI/DVT 开发者协议，非 UI 操作 | 否（隧道即可） | 否 | GPL-3.0 |
| Apple XCUITest/CoreDevice | iOS 官方基线 | 官方 XCUITest；devicectl 仅做进程/安装管理 | 是（XCUITest） | 是 | 闭源/系统自带 |

## 十、iOS 上普遍被吐槽的差距（"gaps everyone complains about on iOS"）

1. **必须要一台 Mac，且需要开发者证书签名**：无论 Maestro、Appium/WDA 还是 agent-device，UI 级控制最终都要在设备上跑一个签名的 XCTest/XCUITest 目标，被称为"macOS tax"。（[iOS CI 的 macOS tax](https://medium.com/@rnovokhatski/ios-automated-tests-in-ci-simulators-webdriveragent-and-the-macos-tax-39d5275836e3)）
2. **WebDriverAgent/XCUITest runner 稳定性差**："flaky"失败十有八九是 WDA 未就绪或弹窗未清理，而非测试逻辑本身；Xcode 26/26.x 与 Appium 3 组合出现"WDA 无法在 iOS 26.0.1 上启动"等新问题。（[Appium issue #21643](https://github.com/appium/appium/issues/21643)）
3. **真机与模拟器能力不对等**：idb 明确表示因 iOS 安全模型限制，物理真机上无法用其做 UI 自动化，只支持模拟器；很多 devicectl 的能力早期只在真机可用、模拟器还在补齐。（[facebook/idb](https://github.com/facebook/idb)，[WWDC 2026 Device Hub](https://bitrise.io/blog/post/wwdc-2026-device-hub-and-what-it-means-for-ci-cd)）
4. **没有公开的、无需 XCTest 的系统级 UI 注入 API**：iOS 不允许通过任何公开 API 或 shell 直接生成 tap/keystroke 事件或截图，只能借道 XCTest/WebDriverAgent 这类"曲线救国"方案。（[Automate iOS devices — the almost Mac-free way](https://daniel-paulus.medium.com/automate-ios-devices-the-almost-mac-free-way-973e8760f9df)）

---

## 结论

iOS 端目前所有严肃方案（Maestro、Appium/WDA、agent-device 乃至间接依赖它们的 Arbigent）殊途同归，最终都落在"设备上跑一个签了名的 XCTest/XCUITest runner"这一层；Apple 新推出的 CoreDevice/devicectl/Device Hub 只解决了设备与进程管理的统一入口，并未开放无障碍树快照或坐标级注入的官方 API，这正是社区反复吐槽的核心缺口。相比之下 Android 端因 Accessibility Service/UIAutomator/ADB 是官方开放能力，mobile-mcp、DroidRun/Mobilerun 等新一代 LLM 原生工具能更轻量地直连真机。
