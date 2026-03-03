# 技术指导 (Tech Guidelines)

## 1. 技术栈强制要求
- **语言**：Python 3.10+
- **并发控制**：`asyncio`
- **动态爬取**：`Playwright` (Async API)
- **DOM 处理**：`BeautifulSoup4` (bs4)
- **格式转换**：`markdownify`（自定义 `MarkdownConverter` 子类，`convert_pre`/`convert_img` 使用 `*args, **kwargs` 签名兼容多版本）
- **严禁项**：本项目中**严禁**引入任何大模型 API（如 OpenAI, Gemini, Anthropic 等）进行数据总结或提取，确保离线纯净转换。

## 2. 编码风格规范 (Coding Style)
- 遵循 PEP 8 规范。
- 必须提供完整的类型提示 (Type Hints)。
- 关键逻辑（尤其是 DOM 节点的剔除逻辑和正则表达式）必须包含简明扼要的中文注释。
- 模块化设计：每个流水线步骤尽量封装为独立的 Class 或 async 函数。

## 3. UI 与交互偏好
- **终端风格**：由于是后台数据处理工具，控制台 (CLI) 的日志输出需要呈现出**极客 (Geek)、科技感**的 UI 风格。
- **日志要求**：避免满屏的毫无意义的 print 刷屏。请使用 `rich` 或 `loguru` 库，实现结构化日志打印。成功、警告、失败需要有明确的颜色区分；在执行批量网页爬取时，推荐使用科技感强的终端进度条（ProgressBar）。

## 4. 关键技术决策记录

### 4.1 DOM 正文容器定位策略
鸿蒙文档在 headless 与 headed 模式下渲染的 CSS 类名可能不同。采用**多候选 fallback 策略**，按优先级逐个尝试：
1. `div.idpContent.markdown-body`（最精确）
2. `div.idpContent`（实际 headless 模式匹配到此）
3. `div.markdown-body`
4. `article`

### 4.2 Discovery 侧边栏展开机制
鸿蒙文档使用 NG-ZORRO `nz-tree` 组件，侧边栏节点是懒加载的。Discovery 模块通过 Playwright 递归点击折叠节点来展开全部层级：
- **注意**：NG-ZORRO 的 CSS 类名使用**下划线** `ant-tree-switcher_close` 而非连字符 `ant-tree-switcher-close`。
- 每轮点击后需等待 DOM 稳定（`waitForTimeout`），最多执行 20 轮。

### 4.3 BS4 代码块标准化
`Tag.new_tag()` 在某些 bs4 版本上不可用（返回 `None`）。改用 `BeautifulSoup` 解析新 HTML 片段后 `replace_with` 的方式创建新节点。

### 4.4 项目目录结构
```
HarmonyOS_RAG_ETL/
├── main.py              # CLI 入口：discover / run
├── requirements.txt     # 依赖清单
├── config/
│   └── config.json      # URL 列表（Discovery 自动生成）
├── src/
│   ├── __init__.py
│   ├── logger.py        # Rich 极客风日志
│   ├── config_loader.py # 配置解析
│   ├── fetcher.py       # Playwright 抓取
│   ├── cleaner.py       # BS4 降噪
│   ├── converter.py     # Markdown 转换
│   ├── exporter.py      # 文件导出
│   └── discovery.py     # URL 自动发现
├── output/              # 输出目录（按分类层级）
└── rules/               # 项目规则文件
```