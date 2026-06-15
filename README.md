# 番茄小说生成器 GUI

一个本地 Windows GUI 工具，用于按番茄小说流程生成：

1. 小说大纲
2. 逐章原稿
3. 番茄去 AI 优化章节
4. 合并全文 `.md` / `.txt`

> 当前版本只生成小说内容，不包含生图、封面图或封面提示词模块。

## 启动

```powershell
cd C:\ai_work\tomato_novel_gui
python app.py
```

或双击：

`start_gui.bat`

## 模型配置

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

- 第一次建议章节数填 `3`，每章 `1000-1500` 字，先测试模型输出质量。
- 确认风格后再生成 `10` 章短篇。
- 如果要封面，请后续单独用其他工具处理，本程序不再生成封面提示词。
