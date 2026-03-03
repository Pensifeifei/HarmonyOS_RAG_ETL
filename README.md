# HarmonyOS RAG ETL Pipeline

一个纯离线的 Python ETL（Extract-Transform-Load）管线，专门用于从 **HarmonyOS Next** 官方开发者文档中批量爬取网页，经过降噪清洗后转换为高保真 Markdown 文件，为企业内网的大模型 **RAG（Retrieval-Augmented Generation）** 系统提供高质量的本地知识库底料。

## ✨ 核心特性

- **智能 URL 发现** — 自动展开华为文档站的 Angular SPA 侧边栏树，递归发现所有文章链接及其层级分类，生成 `config.json` 配置
- **SPA 页面渲染** — 基于 Playwright (Chromium headless) 渲染 Angular SPA，确保动态内容（代码高亮、懒加载等）完整加载
- **深度降噪清洗** — 使用 BeautifulSoup 精确剥离导航栏、面包屑、反馈组件、AI 按钮、代码工具栏等 20+ 种噪声元素
- **高保真 Markdown 转换** — 基于 markdownify 的自定义转换器，精确保留代码围栏（含语言标注）、表格、图片等结构
- **YAML Frontmatter** — 每个输出文件附带结构化元数据（标题、来源 URL、分类、爬取时间），便于下游 RAG 系统索引
- **增量爬取** — 已存在的文件自动跳过，支持断点续爬
- **健壮的错误处理** — 指数退避重试、并发限流、请求间延迟，避免触发反爬机制

## 📁 项目结构

```
HarmonyOS_RAG_ETL/
├── main.py                 # CLI entry point & pipeline orchestrator
├── requirements.txt        # Python dependencies
├── config/
│   └── config.json         # URL list grouped by category (auto-generated or manual)
├── src/
│   ├── discovery.py        # Sidebar tree auto-discovery (Playwright)
│   ├── fetcher.py          # Async page rendering with retry & concurrency
│   ├── cleaner.py          # DOM noise removal (BeautifulSoup)
│   ├── converter.py        # HTML → Markdown conversion (markdownify)
│   ├── exporter.py         # File output with YAML frontmatter
│   ├── config_loader.py    # Config file parser
│   └── logger.py           # Rich-based logging setup
└── rules/                  # Project guidelines & progress tracking
```

## 🔧 环境要求

- Python 3.10+
- Chromium (由 Playwright 自动安装)

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 自动发现文档 URL

从华为文档入口页面自动爬取侧边栏，生成分类配置文件：

```bash
python main.py discover "https://developer.huawei.com/consumer/cn/doc/harmonyos-guides-V5/application-dev-guide-V5"
```

可指定输出路径：

```bash
python main.py discover "https://..." -o config/config.json
```

### 3. 运行 ETL 管线

使用生成的（或手动编写的）配置文件执行完整管线：

```bash
python main.py run
```

#### 常用选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `-c, --config` | 配置文件路径 | `config/config.json` |
| `-o, --output-dir` | 输出目录 | `output/` |
| `--concurrency` | 最大并发数 | `3` |
| `--delay` | 请求间隔（秒） | `1.0` |
| `--overwrite` | 覆盖已有文件 | `False` |

#### 示例

```bash
# 指定配置和输出目录，并发 5，间隔 0.5 秒
python main.py run -c config/config.json -o output/ --concurrency 5 --delay 0.5

# 强制覆盖已有文件
python main.py run --overwrite
```

## ⚙️ ETL 流程

```
URL List (config.json)
    │
    ▼
┌──────────┐   Playwright    ┌──────────┐   BeautifulSoup   ┌──────────┐
│  Fetch   │ ──────────────▶ │  Clean   │ ────────────────▶ │ Convert  │
│ (SPA渲染) │   raw HTML      │ (降噪清洗) │   sanitized DOM   │ (MD转换)  │
└──────────┘                 └──────────┘                   └──────────┘
                                                                  │
                                                                  ▼
                                                           ┌──────────┐
                                                           │  Export  │
                                                           │(YAML+MD) │
                                                           └──────────┘
```

1. **Fetch** — Playwright 渲染 Angular SPA 页面，等待 `div.idpContent` 容器出现，失败时指数退避重试（最多 3 次）
2. **Clean** — BeautifulSoup 定位正文容器，剥离导航、脚注、代码工具栏等噪声元素，标准化 `<ol class="linenums">` 代码块
3. **Convert** — 自定义 markdownify 转换器，保留代码围栏语言标注，修复相对路径图片链接，清除残留 UI 文本
4. **Export** — 生成 YAML frontmatter + Markdown 正文，按分类目录组织输出，支持增量跳过

## 📦 输出格式

每个 Markdown 文件包含 YAML frontmatter 元数据：

```markdown
---
title: TaskPool和Worker的对比
source_url: https://developer.huawei.com/consumer/cn/doc/harmonyos-guides-V5/taskpool-vs-worker-V5
category: 应用框架/ArkTS/ArkTS并发/多线程并发
crawled_at: '2026-03-01T12:00:00Z'
---

# TaskPool和Worker的对比

（正文内容...）
```

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 页面渲染 | [Playwright](https://playwright.dev/python/) (Chromium headless) |
| DOM 解析 | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + [lxml](https://lxml.de/) |
| Markdown 转换 | [markdownify](https://github.com/matthewwithanm/python-markdownify) |
| 终端 UI | [Rich](https://github.com/Textualize/rich) (progress bar, styled logging) |
| 元数据序列化 | [PyYAML](https://pyyaml.org/) |

## 📄 License

MIT
