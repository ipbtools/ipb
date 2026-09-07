# adb 能力边界（research-adb, sonnet, 2026-09-07）

架构：client → host adb server(5037) → 设备 adbd（系统自带常驻守护进程，userdebug 下 root）。USB 首次 RSA 信任弹窗；Wi-Fi：adb tcpip/connect；Android 11+ adb pair 配对码；-s 寻址。
输入：`input tap/swipe/text/keyevent/draganddrop/motionevent`（Java InputManager，单次 tap 数百 ms；`input text` Unicode 不可靠）；`sendevent`（evdev 直写，低延迟）；`getevent`；`monkey`；`uiautomator dump`（accessibility 层 XML，慢，WebView 拿不到语义）；`screencap`/`screenrecord`（按需单帧，`exec-out` 免落盘）。
App/进程/文件：install/uninstall、am start/broadcast/force-stop、pm、push/pull、logcat/bugreport、forward/reverse、`adb shell` 通用逃生舱。
scrcpy：adb push 一个 server jar 到 /data/local/tmp 运行，MediaCodec H.264 经 adb forward 回传，控制通道注入 InputManager.injectInputEvent，35~70 ms 端到端——补足 adb 没有连续画面流与连续手势注入的短板。
安全：开发者选项 + 每台开发机信任；userdebug 下 root；无线配对码把信任锚从物理接触换成网络可达。
Agent 实际依赖的最小闭环：截图 + UI 层级 XML + tap/text/keyevent + 应用启动 + logcat。痛点：uiautomator dump 慢/动态页失败、WebView 无语义、input text Unicode、绝对像素坐标、截图往返。

adb 能力 → iOS 等价必须提供：设备枚举/寻址、USB+无线建链与信任、常驻设备端代理（iOS 只能靠 DDI 服务或签名 app）、UI 结构读取、低延迟坐标注入、Unicode 文本输入、物理键注入、低延迟截图、连续画面流、安装/卸载/启动、日志、文件互传、端口转发。关键差异：iOS 没有 adbd 式 root shell 常驻进程。
来源：developer.android.com/tools/adb；scrcpy README/develop.md；repeato/medium/dev.to 文章。
