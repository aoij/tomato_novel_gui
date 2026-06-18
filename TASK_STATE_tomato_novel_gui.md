# TASK_STATE_tomato_novel_gui

## 当前目标
创建一个 Windows GUI 程序，用于根据番茄小说流程自动生成备选小说方案、大纲、章节正文、优化版文章。

## 成功标准
- 有可运行 GUI。
- 文本模型 base_url / api_key / model 可配置。
- 可输入小说题材、频道、书名、章节数、每章字数、输出目录。
- 可生成多个备选小说方案，并可一键填入主生成页直接使用。
- 自动生成：大纲、章节、优化章节、合并 TXT/MD。
- API Key 不硬编码进源码，默认写入本地 config.local.json 且 gitignore。
- 生图模型模块已移除，不再配置或调用生图接口。
- 封面提示词模块已移除，不再生成 cover 目录或封面提示词文件。

## 已完成
- 初始化项目目录。
- 实现 Tkinter GUI：生成小说页 + 备选方案页 + 文本模型配置页。
- 实现 OpenAI-compatible `/chat/completions` 文本客户端。
- 实现备选小说方案生成、列表展示、详情预览、一键使用选中方案。
- 实现大纲 JSON 生成、逐章生成、番茄去AI优化、摘要续写、合并全文。
- 已移除生图模型配置、GUI 控件、`/images/generations` 调用和本地配置中的 image 字段。
- 已移除封面提示词生成逻辑、cover 输出目录、README 输出说明。
- 写入 `README.md` 和 `start_gui.bat`。
- 已通过 `python -m py_compile app.py` 语法检查。

## 正在做
- 已完成，待用户运行 GUI 测试。

## 阻塞点
无。API Key 需用户在 GUI 中填写并保存到本地 `config.local.json`。

## 下一步
用户可运行：`C:\ai_work\tomato_novel_gui\start_gui.bat`

## 关键文件
- `C:\ai_work\tomato_novel_gui\app.py`
- `C:\ai_work\tomato_novel_gui\README.md`
- `C:\ai_work\tomato_novel_gui\start_gui.bat`
- `C:\ai_work\tomato_novel_gui\config.example.json`
- `C:\ai_work\tomato_novel_gui\.gitignore`

## 最后更新时间
2026-06-18
