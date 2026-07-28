# SZU Network Guardian

[![Build Windows EXE](https://github.com/Georgeupup/szu-network-guardian/actions/workflows/build-windows.yml/badge.svg)](https://github.com/Georgeupup/szu-network-guardian/actions/workflows/build-windows.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows11&logoColor=white)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

一个简洁、轻量的深圳大学校园网断线监控与自动重连工具。

支持新版教学/办公区深澜 SRun 认证、宿舍区 ePortal 认证、系统托盘、开机自启和安全凭据存储。

## 功能特性

- 简约的 Windows 图形界面
- 手动选择教学/办公区或宿舍区，避免校园网网关互通造成误判
- 提供实验性的自动顺序尝试模式，优先尝试教学区
- 定时检测直连网络状态，避免代理造成在线误判
- 教学/办公区使用 SRun challenge 加密认证
- 宿舍区使用 ePortal 认证接口
- 仅在断网时尝试登录，不会在联网正常时重复认证
- 认证成功后分阶段复查外网，避免过早报告失败
- 最小化或关闭窗口后进入系统托盘继续运行
- 托盘菜单支持打开界面、立即检测和退出
- 支持当前 Windows 用户开机自启，无需管理员权限
- 使用 Windows DPAPI 加密保存密码
- 界面仅保留最近 3 小时日志
- 完整日志按天保存，自动删除 7 天前的日志
- 支持 PyInstaller 单文件 EXE 和 GitHub Actions 自动构建

## 系统要求

- Windows 10 或 Windows 11
- 运行源码时需要 Python 3.10 或更高版本
- 已连接 `SZU_WLAN` 或深圳大学校园有线网络

> [!NOTE]
> 本程序负责网络链路建立后的校园网认证。如果关闭 Wi-Fi、拔出网线或在 Windows 中主动断开无线网络，请先恢复物理网络连接。建议为 `SZU_WLAN` 开启“自动连接”。

## 快速开始

### 方式一：下载 Release（推荐）

不需要安装 Python，适合大多数用户：

1. 打开 [Releases 页面](https://github.com/Georgeupup/szu-network-guardian/releases/latest)。
2. 下载最新版 `SZU-Network-Guardian-v*.exe`。
3. 双击 EXE 即可运行，无需安装。

### 首次使用

1. 输入校园网账号和统一身份认证密码。
2. 按电脑的实际位置选择区域：实验室电脑选择“教学 / 办公区”，宿舍电脑选择“宿舍区”。不建议长期无人值守的电脑使用实验性自动模式。
3. 设置检测间隔，推荐 3～5 分钟。
4. 根据需要勾选“开机自动启动”。
5. 点击“开始守护”。
6. 最小化或关闭窗口，程序会进入系统托盘继续监控。

### 方式二：使用源码运行

```powershell
git clone https://github.com/Georgeupup/szu-network-guardian.git
cd szu-network-guardian
python -m pip install -r requirements.txt
python main.py
```

## 构建 Windows EXE

双击 `build.bat`，或在 PowerShell 中运行：

```powershell
.\build.ps1
```

构建脚本会创建独立的 `.venv-build` 环境、执行自动化测试，并生成：

```text
dist\SZU-Network-Guardian-v1.1.1.exe
```

也可以在仓库的 [Actions 页面](https://github.com/Georgeupup/szu-network-guardian/actions/workflows/build-windows.yml) 手动运行 `Build Windows EXE`，然后下载构建产物。

> [!IMPORTANT]
> 请先把 EXE 移动到最终位置，再勾选“开机自动启动”。开机启动项会记录 EXE 的当前位置；移动文件后需要取消并重新勾选。

## 配置与日志

配置文件：

```text
%LOCALAPPDATA%\SZUNetworkGuardian\config.json
```

完整日志：

```text
%LOCALAPPDATA%\SZUNetworkGuardian\logs
```

日志使用 `guardian-YYYY-MM-DD.log` 命名。程序启动时和运行期间会自动清理 7 天前的日志。

开机自启使用当前用户注册表项：

```text
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
```

## 认证接口

| 网络区域 | 认证方式 | 地址 |
| --- | --- | --- |
| 教学 / 办公区 | 深澜 SRun challenge 登录 | `https://net.szu.edu.cn` |
| 宿舍区 | ePortal 登录 | `http://172.30.255.42:801/eportal/portal/login/` |

教学区已经从旧版 Dr.COM 简单表单迁移到带 challenge 的 SRun 认证。相关实现集中在：

- `szu_guardian/srun.py`：SRun 加密和登录流程
- `szu_guardian/network.py`：区域识别、联网检测和重连流程
- `szu_guardian/monitor.py`：后台监控调度
- `szu_guardian/tray.py`：Windows 系统托盘

## 项目结构

```text
.
├── .github/workflows/       # Windows 自动构建
├── szu_guardian/
│   ├── local_log.py         # 本地日志与自动清理
│   ├── monitor.py           # 后台监控
│   ├── network.py           # 网络检测与认证入口
│   ├── srun.py              # SRun 协议实现
│   ├── startup.py           # Windows 开机自启
│   ├── storage.py           # DPAPI 配置存储
│   ├── tray.py              # 系统托盘
│   └── ui.py                # 图形界面
├── tests/                   # 自动化测试
├── build.ps1                # Windows 打包脚本
├── main.py                  # 程序入口
└── requirements.txt
```

## 隐私与安全

- 源码和构建产物不包含预设账号或密码。
- 运行日志不会输出密码、认证 challenge 或完整认证载荷。
- 密码通过 Windows DPAPI 加密，通常只能由保存它的同一 Windows 用户解密。
- 请勿把 `%LOCALAPPDATA%\SZUNetworkGuardian\config.json` 上传到公共仓库。

## Acknowledgements / 致谢

本项目在以下开源项目和公开技术资料的基础上完成，感谢原作者与贡献者：

- [ackness/szu-autoconnect](https://github.com/ackness/szu-autoconnect)：本项目最初参考的深圳大学校园网自动重连脚本，包括旧版 Dr.COM 登录思路和基础监控结构。
- [Sleepstars/SZU-login](https://github.com/Sleepstars/SZU-login)：提供新版深圳大学教学/办公区 SRun、宿舍区 ePortal 接口及登录流程的重要参考。
- [vidar-team/srun-login](https://github.com/vidar-team/srun-login)：SRun challenge、XXTEA/XEncode、校验和与自定义 Base64 流程的上游实现。
- E99p1ant 及上述项目的所有贡献者：感谢其在 SRun 协议实现与开源维护方面的工作。

`szu_guardian/srun.py` 包含基于 MIT 许可实现的 Python 移植。第三方归属和许可说明请参阅 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 贡献

欢迎提交 Issue 和 Pull Request。若学校调整认证方式，请附上脱敏后的响应格式或错误日志，切勿提交真实账号、密码或认证数据。

## 许可证

本项目采用 [MIT License](LICENSE)。

## 免责声明

本项目仅用于维护本人账号的正常校园网连接。请遵守学校网络管理规定；因认证接口变更、账号状态、网络环境或不当使用导致的问题，项目作者不承担责任。
