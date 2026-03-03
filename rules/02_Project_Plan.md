# 项目计划 (Project Plan)

## 1. 核心目标
放弃依赖外部大模型（如 Gemini）的总结提炼，搭建一条**100% 确定性、无幻觉**的数据抓取与转换链路。确保官方文档中的 API 参数表格和代码块 (Code Blocks) 能被完美无损地提取并切片。

## 2. 核心流水线设计
项目包含以下 6 个核心模块 + 1 个 CLI 入口，以流式管线的方式运行：
1. **Config Loader** (`src/config_loader.py`)：基于 `config.json` 解析需要爬取的分类与目标 URL 列表。
2. **Fetcher** (`src/fetcher.py`)：Playwright 异步渲染 SPA 单页应用，处理网络重试（3 次）与超时，获取完整渲染后的 DOM。
3. **Cleaner** (`src/cleaner.py`)：BeautifulSoup4 剔除网页噪音节点，多候选选择器 fallback 策略定位正文容器（`div.idpContent` 等），代码块标准化。
4. **Converter** (`src/converter.py`)：markdownify 自定义转换器，`*args, **kwargs` 签名兼容多版本，保留代码高亮标签和表格。
5. **Exporter** (`src/exporter.py`)：按分类目录层级保存，自动注入 YAML Frontmatter 元数据，支持增量跳过。
6. **Discovery** (`src/discovery.py`)：Playwright 自动递归展开侧边栏目录树（NG-ZORRO `nz-tree`），提取全部文章 URL 并按层级分类，生成 `config.json`。
7. **入口** (`main.py`)：CLI 支持 `discover`（URL 发现）和 `run`（完整 ETL）两个子命令，含进度条和统计汇总。

## 3. 验收标准
- 脚本支持断点续传/增量抓取（已抓取的文件跳过）。
- 生成的 Markdown 在本地查看时，表格不乱码换行，代码缩进正确。
- Discovery 模块能自动从指南首页提取完整 URL 列表（实测 627 分类、3146 URL）。
- `main.py run` 全流程 Fetch → Clean → Convert → Export 无报错通过。