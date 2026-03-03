# 项目进度 (Project Progress)

> **AI 行为指令**：在执行完每一项任务后，你必须更新此文件，将对应的 `[ ]` 修改为 `[x]`，并在下方“Bug 与问题记录”区追加你在开发中遇到的问题及解决方案。

## 阶段 1：项目初始化与基础设施
- [x] 1.1 初始化 Python 虚拟环境，生成 `requirements.txt`。
- [x] 1.2 搭建项目基本目录结构 (`src/`, `output/`, `config/`)。
- [x] 1.3 编写全局日志模块，配置极客风的 CLI 输出格式。

## 阶段 2：核心流水线开发
- [x] 2.1 编写配置解析模块，读取目标 URL 列表。
- [x] 2.2 配置 Playwright 异步抓取引擎，实现超时与重试机制。
- [x] 2.3 编写 BeautifulSoup DOM 降噪逻辑（精准定位鸿蒙官网正文）。
- [x] 2.4 集成 Markdown 转换器，重点调试 Table 和 Code Block 的还原度。
- [x] 2.5 编写 Exporter 模块，生成带 Frontmatter 元数据的 `.md` 文件并实现增量跳过。

## 阶段 3：总成与测试
- [x] 3.1 编写 `main.py` 作为入口点，串联完整 ETL 流程（支持 `discover` / `run` 子命令）。
- [x] 3.2 使用 2 个真实 URL（含代码块和表格）实测通过：2/2 Success, 0 Failed。
- [x] 3.3 验证输出文件格式：YAML frontmatter + 结构化 Markdown，无乱码。

## 增强优化
- [x] Cleaner 降噪增强：新增 6 个噪声选择器（代码块工具栏、悬浮提示、锚点图标、底部导航、展开按钮、AI 按钮）。
- [x] Converter 后处理增强：正则清除残留 UI 噪声文本（`收起`/`自动换行`/`深色代码主题`/`复制`）+ 图片相对路径绝对化。
- [x] main.py 全量运行增强：日志持久化到 `output/etl.log` + `--delay` 请求间延迟参数（默认 1 秒）。
- [x] 验证通过：噪声从 28 处/篇降为 0。

---

## 🐛 Bug 与问题记录 (Bug & Issue Tracker)
*(AI 需在此处实时追加记录)*

- **[2026-03-02]** - **pip 版本警告**：pip 21.2.4 落后于 26.0.1 | **[解决方案]**：非阻塞性警告，不影响功能，后续视需要升级。
- **[2026-03-02]** - **Cleaner 选择器不匹配**：`div.idpContent.markdown-body` 在 headless 模式下找不到 | **[解决方案]**：改为多候选 fallback 策略，实际匹配到 `div.idpContent`。
- **[2026-03-02]** - **Tag.new_tag() 不可用**：bs4 某些版本 Tag 对象上 `new_tag` 为 None | **[解决方案]**：改用 `BeautifulSoup` 解析新 HTML 片段再 `replace_with`。
- **[2026-03-02]** - **markdownify callback 签名不兼容**：不同调用路径传参不一致 | **[解决方案]**：`convert_pre`/`convert_img` 改用 `*args, **kwargs` 签名。
- **[2026-03-02]** - **Discovery 侧边栏展开选择器**：NG-ZORRO CSS 类名使用下划线 `_close` 而非连字符 `-close` | **[解决方案]**：修正为 `ant-tree-switcher_close`。
- **[2026-03-02]** - **代码块前 UI 噪声残留**（28 处/篇）：`收起`/`自动换行`/`深色代码主题`/`复制` | **[解决方案]**：Cleaner 新增 `.highlight-div-header` 等 6 个噪声选择器 + Converter 后处理正则双重保险。