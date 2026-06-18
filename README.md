# 番茄小说生成器 GUI

一个本地 Windows GUI 工具，用于按番茄小说流程生成：

1. 备选小说方案
2. 小说大纲
3. 逐章原稿
4. 番茄去 AI 优化章节
5. 合并全文 `.md` / `.txt`

> 当前版本只生成小说内容，不包含生图、封面图或封面提示词模块。

## 启动

```powershell
cd C:\ai_work\tomato_novel_gui
python app.py
```

或双击：

`start_gui.bat`

## 功能说明

### 备选方案

在“备选方案”页可以输入想法/关键词，选择男频、女频或不限，然后生成多个备选小说方案。

每个备选方案包含：

- 书名
- 频道
- 类型
- 一句话卖点
- 核心创意
- 开篇钩子
- 爽点
- 避坑提醒

选中方案后点击“使用选中方案”，会自动填入“生成小说”页，可直接开始生成。

### 生成小说

生成流程：

```text
大纲 JSON → 可读大纲 → 原始章节 → 番茄去AI优化章节 → 合并全文 TXT/MD
```

### 模型配置

GUI 里有“模型配置”页，可配置文本模型：

- Base URL
- API Key
- Model
- Temperature
- Timeout

默认模型配置：

- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
- Model: `mimo-v2.5`

## API Key 安全

- API Key 不写入源码。
- GUI 保存后会写入本机：`config.local.json`
- `config.local.json` 已加入 `.gitignore`。
- 不要把 `config.local.json` 分享给别人。

## 输出目录结构

每本小说会生成一个独立文件夹，默认在：

`C:\小说\短篇`

结构示例：

```text
小说名/
  outline.json
  outline.md
  chapters_raw/
  chapters_optimized/
    第01章_xxx.md
    第01章_xxx.txt
  全文_原稿.md
  全文_番茄去AI优化版.md
  全文_番茄去AI优化版.txt
  README.md
```

## 使用建议

- 不知道写什么时，先用“备选方案”生成 5-10 个选题。
- 第一次建议章节数填 `3`，每章 `1000-1500` 字，先测试模型输出质量。
- 确认风格后再生成 `10` 章短篇。
- 如果要封面，请后续单独用其他工具处理，本程序不再生成封面提示词。
