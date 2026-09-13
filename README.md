# 🚩 博客下载助手(CTFer)

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Target](https://img.shields.io/badge/target-CTF_Knowledge_Base-orange.svg)
![Playwright](https://img.shields.io/badge/powered%20by-Playwright-008080.svg)

**博客下载助手(CTFer)** 是一款专为 CTFer 打造(不仅限于CTFer)的线下赛本地知识库构建工具。它可以快速将先知社区、博客园、CSDN 上的高质量 Writeup、漏洞分析和工具脚本转换为 Markdown 文档，方便在无网环境下通过 Obsidian 或 Typora 等笔记软件进行检索与查阅。(已在https://linux.do 发帖)

[本项目灵感来自于学长[YZBRH (BR)](https://github.com/YZBRH)的博客下载助手，对其进行了浏览器的脱离]

作者：debu8ger([incldue](https://github.com/incldue))



## 🎯 为什么需要它？

在 AWD、AWDP 或传统的解题赛中，线下环境通常断网或网络极差，如果什么知识点忘了还不能在线搜。

- **离线查阅**：一键同步先知社区、CSDN 、博客园等的深度分析文章。
- **纯净阅读**：自动剔除网页广告福利、评论区、右侧工具栏，只保留核心 Payload 和解析。



## ✨ 特性

- **先知社区专项优化**：
  - **精准定位**：根据前端代码，强制锁定 `.left_container` 核心正文，过滤干扰。
  - **极致去杂(可能还有bug)**：自动清理 `#news_toolbar` (作者信息/浏览量) 和 `.detail_share` (分享/评论)。
- **验证码友好处理**：
  - 下载博客园文章时，程序会自动弹出窗口，方便你在批量下载时快速手动处理滑块验证。
  - 下载先知社区和 CSDN 时使用 **Headless 模式**。
- **跨平台浏览器支持**：支持自动检测 macOS / Windows / Linux 上常见的 Chromium 内核浏览器。
- **可选择本地浏览器**：既可使用 `playwright install chromium` 安装的浏览器，也可自由选择本机浏览器路径。
- **更友好的状态反馈**：搜索与下载过程中会在界面底部实时显示当前进度。
- **更顺手的桌面 UI**：新增平台筛选、结果统计、批量选择、双击打开文章、导出目录直达等交互。
- **预览/付费页识别**：遇到 CSDN 这类“仅显示预览、需要解锁全文”的文章时，会直接提示失败原因，避免导出残缺内容。



## ❗目前存在的问题

- **部分站点仍有验证码/风控**：尤其是博客园，批量搜索时仍可能需要手动过验证。
- **下载的 `.md` 文件排版仍可继续优化**：尽管 CSDN、博客园的部分文章能较好渲染，但先知社区的图片和站点导航痕迹还有优化空间。
- **反应速度较慢**：自动化爬取使得必须模拟人类阅读，拉取页面响应速度会被明显拉低。



## 🛠️ 快速部署

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2.启动！

```bash
终端运行：python main.py
```

> 如果本机已安装 Chrome / Edge 等浏览器，可直接在界面中点击“自动检测”；若浏览器路径留空，则默认使用 Playwright 自带 Chromium。



## 🎯 专题预设（本项目新增）

做 pwn / 逆向 / web 时想一次性囤齐某个方向的资料，不必手动想关键词。仓库根目录的 `topics.json` 定义了一组**专题**：每个专题 = 一批检索关键词 + 一套标题打分规则。

内置 **22 个专题**，覆盖 pwn、web 两条线的解题与 AWDP 攻防两侧：

**PWN 解题**

| 专题 id | 名称 |
|---|---|
| `pwn-heap-exploit` | 堆利用（tcache / fastbin / unsorted bin / UAF / house of） |
| `pwn-stack-rop` | 栈溢出 / ROP（ret2libc、ret2csu、栈迁移、canary 绕过） |
| `pwn-format-string` | 格式化字符串（任意读 / 任意写） |
| `pwn-kernel` | 内核提权（QEMU 环境、内核 UAF、modprobe_path） |
| `pwn-sandbox-orw` | 沙箱绕过 / ORW shellcode |
| `pwn-tools` | 工具链与调试（pwntools / pwndbg / GEF / one_gadget） |

**PWN 修复与补丁**

| 专题 id | 名称 |
|---|---|
| `pwn-patch-binary` | 二进制 patch 实战（IDA/Ghidra 打补丁、crackme） |
| `pwn-patch-1day` | 补丁对比 / 1-day 分析（BinDiff、Diaphora） |
| `pwn-patchelf-libc` | patchelf / libc 环境修复 |

**WEB 解题**

| 专题 id | 名称 |
|---|---|
| `web-sqli` | SQL 注入（盲注、堆叠、二次注入、宽字节、WAF 绕过） |
| `web-xss` | XSS / CSRF（反射/存储/DOM、打点） |
| `web-ssti` | SSTI 模板注入（Jinja2 / Twig / Freemarker） |
| `web-ssrf` | SSRF（gopher/dict、打内网） |
| `web-upload-rce` | 文件上传 / RCE（.user.ini、解析漏洞、命令执行绕过） |
| `web-deserialization` | 反序列化（PHP unserialize / phar、Java、fastjson） |
| `web-php-tricks` | PHP 特性绕过（弱类型、伪协议、disable_functions） |
| `web-lfi-traversal` | 文件包含 / 目录穿越（LFI、日志包含） |

**AWDP 攻防（进攻 + 修包）**

| 专题 id | 名称 |
|---|---|
| `awdp-pwn-attack` | 进攻 · PWN（漏洞定位、批量打、exp 自动化） |
| `awdp-pwn-fix` | 修包 · PWN（最小 diff 堵洞，原始 exp 验证） |
| `awdp-web-attack` | 进攻 · WEB（批量 getshell、不死马、权限维持） |
| `awdp-web-fix` | 修包 · WEB（改最小 diff、补 WAF 规则） |
| `awd-common` | 通用打法（流量分析、查杀、应急排查、得分策略） |

**打分规则**：搜索结果里 `patch`、`注入` 这类词太泛（CSDN 会把 “git patch”、“MySQL 索引优化” 全捞进来），所以按标题加权打分而不是简单包含——强相关词（pwn/tcache/反序列化…）加 3 分，一般相关词（利用/绕过/实战…）加 2 分，噪音词（git/前端/java堆/sql优化…）扣 4 分，总分 ≥ `min_score` 才收录。

**GUI 用法**：顶部「专题预设」下拉选一个专题 → 点「专题抓取」，程序会依次搜完该专题的全部关键词，过滤去重后列出结果，再勾选导出。

**新增/修改专题**：直接编辑 `topics.json`（加一个 `keywords` + `score_terms` 块即可），重启程序生效。

### 无 GUI 批量抓取（cli.py）

服务器或想在终端里一次性建库时用 `cli.py`：

```bash
python cli.py --list-topics                        # 看所有专题
python cli.py --topic pwn-heap-exploit --pages 2 --limit 10 --out knowledge
python cli.py --topic web-sqli,web-ssti --limit 8  # 逗号分隔，串行跑多个专题
python cli.py --topic all --pages 2 --limit 6      # 全量跑 22 个专题（同 --all-topics）
python cli.py --keyword "patchelf rpath" --sites CSDN --limit 5 --out knowledge
python cli.py --topic pwn-heap-exploit --dry-run    # 只看命中列表，不下载
```

常用参数：`--sites`（平台白名单，默认 `CSDN,先知社区`）、`--delay`（每篇间隔秒数，默认 3，调大更不容易被风控）、`--retries`（单篇重试次数）、`--show-browser`（有头模式，过博客园滑块验证时用）。

导出结构（可直接丢进 Obsidian 当库）：

```
knowledge/pwn-patch-binary/
├── index.md                      # 全专题索引
└── <文章标题>/
    ├── <文章标题>.md
    └── images/image_1.png ...    # 图片已本地化，断网也能看图
```



## 📦 项目清单

- `browser_utils.py`: 负责浏览器路径检测与解析。
- `puller.py`: 负责各平台搜索接口实现。
- `downloader.py`: 渲染、去杂及 Markdown 转换。
- `gui.py`: 实现桌面 UI 与异步任务调度。
- `main.py`: 项目入口。
- `topics.json` / `topics.py`: 专题预设配置与打分过滤。
- `cli.py`: 无 GUI 批量抓取入口。
- `requirements.txt`: 所需下载依赖环境。



## 🩹 抓取健壮性说明（本项目新增）

- **风控识别与退避重试**：CSDN 会间歇性返回「请进行安全验证」拦截页。下载器会显式识别该页面，并做退避重试（默认 3 次，间隔 5s/10s/15s），实测能把成功率从 1/6 拉到 6/6。
- **图片懒加载处理**：先滚动整页触发 `IntersectionObserver`，再回顶提取；同时补齐 `data-actualsrc / data-src / data-original / data-lazy-src / data-echo / data-url / file` 等各家懒加载属性，并清理 `srcset`（否则 html2text 会生成重复条目）。
- **正文容器选择**：改为「按具体度取第一个达标容器」而非「取文本最长的容器」。后者会一路选到最外层 `article`，把 CSDN 的「原创/发布时间/阅读量/收录于」头部块一起导出。



## 🤝 贡献与反馈

如果你在使用过程中发现新的去杂需求或 Bug，欢迎提交 Issue。



## 📄 许可说明

本项目遵循 MIT 开源协议，仅供技术交流与学习使用，请勿用于大规模商业爬取，并尊重各平台的 Robots 协议；仅限用于个人本地知识库构建。在比赛中请遵守赛制规则，尊重原创内容版权。
