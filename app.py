#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄小说生成器 GUI
- 可配置 OpenAI-compatible 文本模型
- 流程：设定 -> 大纲 -> 章节 -> 优化 -> TXT/MD
"""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.local.json"
CONFIG_EXAMPLE_PATH = APP_DIR / "config.example.json"

DEFAULT_CONFIG = {
    "text": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "api_key": "",
        "model": "mimo-v2.5",
        "temperature": 0.8,
        "timeout": 180,
    },
    "app": {
        "default_output_dir": r"C:\小说\短篇",
    },
}


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG
    if CONFIG_PATH.exists():
        try:
            cfg = deep_merge(cfg, json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", name).strip()
    return name[:80] or "未命名小说"


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json(text: str) -> Any:
    text = strip_code_fence(text)
    try:
        return json.loads(text)
    except Exception:
        pass
    # 尝试截取第一段 JSON 对象
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("模型输出不是合法 JSON")


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + path
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {raw}") from e

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.8, max_tokens: Optional[int] = None) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        obj = self._post_json("/chat/completions", payload)
        try:
            return obj["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"无法解析 chat/completions 响应: {obj}") from e



@dataclass
class NovelJob:
    title: str
    channel: str
    genre: str
    premise: str
    chapters: int
    words_per_chapter: int
    output_root: Path
    author_name: str = "昨页"


SYSTEM_PROMPT = """你是专业番茄小说主编与网文生成助手。严格输出用户要求的格式，不要输出思考过程。写作风格：短段落、高冲突、强钩子、强爽点、对话独立、适合手机竖屏阅读。避免空泛套话，优先具体动作、具体反转、具体情绪。"""


def prompt_outline(job: NovelJob) -> str:
    return f"""
请为一部番茄小说生成完整创作大纲，必须输出合法 JSON，不要 Markdown，不要代码块。

要求：
- 书名：{job.title or '请根据题材生成'}
- 频道：{job.channel}
- 类型：{job.genre}
- 核心创意：{job.premise}
- 章节数：{job.chapters}
- 每章目标字数：{job.words_per_chapter}
- 风格：番茄小说，短段、高冲突、强钩子、每章一个爽点或反转。

JSON 格式：
{{
  "title": "书名",
  "logline": "一句话卖点",
  "genre": "类型",
  "tags": ["标签1", "标签2"],
  "main_characters": [
    {{"name": "角色名", "role": "身份", "arc": "人物弧光"}}
  ],
  "selling_points": ["爽点1", "爽点2"],
  "world_rules": ["设定规则1", "设定规则2"],
  "chapter_outlines": [
    {{"chapter": 1, "title": "第1章标题", "hook": "开章钩子", "beats": ["情节点1", "情节点2", "情节点3"], "ending_hook": "章末钩子"}}
  ]
}}
""".strip()


def prompt_chapter(job: NovelJob, outline: Dict[str, Any], chapter_outline: Dict[str, Any], previous_summary: str) -> str:
    return f"""
请根据大纲写第 {chapter_outline.get('chapter')} 章正文，只输出章节正文，不要解释，不要 Markdown 代码块。

全书信息：
书名：{outline.get('title', job.title)}
一句话卖点：{outline.get('logline', '')}
类型：{outline.get('genre', job.genre)}
核心爽点：{json.dumps(outline.get('selling_points', []), ensure_ascii=False)}
主要角色：{json.dumps(outline.get('main_characters', []), ensure_ascii=False)}

上一章摘要：
{previous_summary or '无，当前为第一章'}

本章大纲：
{json.dumps(chapter_outline, ensure_ascii=False, indent=2)}

写作要求：
1. 标题格式：第{chapter_outline.get('chapter')}章 {chapter_outline.get('title', '')}
2. 每段尽量 1-2 句，适合番茄手机端。
3. 对话独立成段。
4. 开头 300 字内必须出现冲突或悬念。
5. 结尾必须有钩子或情绪落点。
6. 字数目标约 {job.words_per_chapter} 字，可上下浮动 20%。
7. 不要写“本章完”。
""".strip()


def prompt_polish(job: NovelJob, chapter_text: str) -> str:
    return f"""
请按番茄小说去 AI 化规则优化下面章节。只输出优化后的正文，不要说明。

优化规则：
- 保留原剧情和角色关系，不新增大事件。
- 短段落，高频换行，对话独立。
- 删除空泛解释，增加具体动作、表情、现场压迫感。
- 强化爽点、反转、情绪爆点。
- {job.channel} 频道语感：男频偏热血逆袭、强者归来、打脸；女频偏清醒成长、虐渣反击、情感拉扯。
- 可适量使用“！！！”“……”等情绪标点，但不要过度。
- 不要输出“优化完成”等元说明。

原文：
{chapter_text}
""".strip()


def prompt_summary(chapter_text: str) -> str:
    return f"""
请用 150 字以内总结这一章的关键信息，供下一章续写使用。只输出摘要。

章节正文：
{chapter_text}
""".strip()



class NovelGenerator:
    def __init__(self, text_client: OpenAICompatibleClient, temperature: float, log):
        self.text_client = text_client
        self.temperature = temperature
        self.log = log

    def chat(self, user_prompt: str, max_tokens: Optional[int] = None) -> str:
        return self.text_client.chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ], temperature=self.temperature, max_tokens=max_tokens)

    def run(self, job: NovelJob) -> Path:
        title_hint = job.title.strip() or f"番茄小说_{time.strftime('%Y%m%d_%H%M%S')}"
        project_dir = job.output_root / safe_filename(title_hint)
        project_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = project_dir / "chapters_raw"
        opt_dir = project_dir / "chapters_optimized"
        for d in (raw_dir, opt_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.log("生成大纲...")
        outline_text = self.chat(prompt_outline(job), max_tokens=12000)
        (project_dir / "outline_raw_response.txt").write_text(outline_text, encoding="utf-8")
        outline = extract_json(outline_text)
        if not job.title.strip():
            job.title = outline.get("title") or title_hint
        (project_dir / "outline.json").write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
        (project_dir / "outline.md").write_text(self.outline_to_md(outline), encoding="utf-8")

        chapters = outline.get("chapter_outlines") or []
        if not chapters:
            raise RuntimeError("大纲里没有 chapter_outlines")
        chapters = chapters[: job.chapters]

        previous_summary = ""
        raw_parts = [f"# {outline.get('title', job.title)}\n"]
        opt_parts_md = [f"# {outline.get('title', job.title)}（番茄去AI优化版）\n"]
        opt_parts_txt = [f"{outline.get('title', job.title)}（番茄去AI优化版）\n"]

        for idx, ch in enumerate(chapters, start=1):
            ch_no = int(ch.get("chapter") or idx)
            ch_title = str(ch.get("title") or f"第{ch_no}章")
            self.log(f"生成第 {ch_no}/{len(chapters)} 章：{ch_title}")
            raw = self.chat(prompt_chapter(job, outline, ch, previous_summary), max_tokens=12000)
            raw = strip_code_fence(raw).strip() + "\n"
            raw_path = raw_dir / f"第{ch_no:02d}章_{safe_filename(ch_title)}.md"
            raw_path.write_text(raw, encoding="utf-8")
            raw_parts.append(raw)

            self.log(f"优化第 {ch_no}/{len(chapters)} 章...")
            polished = self.chat(prompt_polish(job, raw), max_tokens=12000)
            polished = strip_code_fence(polished).strip() + "\n"
            opt_path = opt_dir / f"第{ch_no:02d}章_{safe_filename(ch_title)}.md"
            txt_path = opt_dir / f"第{ch_no:02d}章_{safe_filename(ch_title)}.txt"
            opt_path.write_text(polished, encoding="utf-8")
            txt_path.write_text(self.md_to_txt(polished), encoding="utf-8")
            opt_parts_md.append(polished)
            opt_parts_txt.append(self.md_to_txt(polished))

            self.log(f"摘要第 {ch_no}/{len(chapters)} 章...")
            previous_summary = self.chat(prompt_summary(polished), max_tokens=1000).strip()

        (project_dir / "全文_原稿.md").write_text("\n\n".join(raw_parts), encoding="utf-8")
        (project_dir / "全文_番茄去AI优化版.md").write_text("\n\n".join(opt_parts_md), encoding="utf-8")
        (project_dir / "全文_番茄去AI优化版.txt").write_text("\n\n".join(opt_parts_txt), encoding="utf-8")


        readme = f"""# {outline.get('title', job.title)}

## 输出内容

- `outline.json`：结构化大纲
- `outline.md`：可读大纲
- `chapters_raw/`：原始章节
- `chapters_optimized/`：番茄去AI优化章节，含 `.md` 和 `.txt`
- `全文_原稿.md`
- `全文_番茄去AI优化版.md`
- `全文_番茄去AI优化版.txt`

## 生成参数

```json
{json.dumps(asdict(job), ensure_ascii=False, indent=2, default=str)}
```

## 生成时间

{time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        (project_dir / "README.md").write_text(readme, encoding="utf-8")
        self.log(f"完成：{project_dir}")
        return project_dir

    @staticmethod
    def md_to_txt(text: str) -> str:
        lines = []
        for line in text.splitlines():
            m = re.match(r"^(#{1,6})\s+(.*)$", line)
            lines.append(m.group(2) if m else line)
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def outline_to_md(outline: Dict[str, Any]) -> str:
        parts = [f"# {outline.get('title', '未命名')} - 大纲\n"]
        for key in ("logline", "genre"):
            if outline.get(key):
                parts.append(f"## {key}\n\n{outline[key]}\n")
        if outline.get("tags"):
            parts.append("## 标签\n\n" + "、".join(outline["tags"]) + "\n")
        if outline.get("selling_points"):
            parts.append("## 核心爽点\n\n" + "\n".join(f"- {x}" for x in outline["selling_points"]) + "\n")
        if outline.get("main_characters"):
            parts.append("## 主要角色\n")
            for c in outline["main_characters"]:
                parts.append(f"- **{c.get('name','')}**：{c.get('role','')}；{c.get('arc','')}\n")
        if outline.get("chapter_outlines"):
            parts.append("\n## 章节大纲\n")
            for ch in outline["chapter_outlines"]:
                parts.append(f"\n### 第{ch.get('chapter')}章 {ch.get('title','')}\n")
                parts.append(f"- 开章钩子：{ch.get('hook','')}\n")
                for b in ch.get("beats", []):
                    parts.append(f"- {b}\n")
                parts.append(f"- 章末钩子：{ch.get('ending_hook','')}\n")
        return "".join(parts)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("番茄小说生成器")
        self.geometry("980x760")
        self.cfg = load_config()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.build_ui()
        self.after(200, self.drain_logs)

    def v(self, value="") -> tk.StringVar:
        return tk.StringVar(value=str(value))

    def build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        gen = ttk.Frame(nb)
        cfg_tab = ttk.Frame(nb)
        nb.add(gen, text="生成小说")
        nb.add(cfg_tab, text="模型配置")

        self.vars: Dict[str, tk.StringVar] = {}
        app_cfg = self.cfg.get("app", {})
        text_cfg = self.cfg.get("text", {})

        # 生成页
        form = ttk.LabelFrame(gen, text="小说参数")
        form.pack(fill="x", padx=8, pady=8)
        self.vars["title"] = self.v("我都成首富了，你说我是废物？")
        self.vars["channel"] = self.v("男频")
        self.vars["genre"] = self.v("都市赘婿 / 身份曝光 / 商战复仇 / 打脸爽文")
        self.vars["chapters"] = self.v("10")
        self.vars["words"] = self.v("1200")
        self.vars["author"] = self.v("昨页")
        self.vars["output"] = self.v(app_cfg.get("default_output_dir", r"C:\小说\短篇"))

        rows = [
            ("书名", "title"),
            ("频道", "channel"),
            ("类型", "genre"),
            ("章节数", "chapters"),
            ("每章字数", "words"),
            ("作者名", "author"),
            ("输出目录", "output"),
        ]
        for i, (label, key) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=5)
            if key == "channel":
                ttk.Combobox(form, textvariable=self.vars[key], values=["男频", "女频", "双频/其他"], width=38).grid(row=i, column=1, sticky="we", padx=6, pady=5)
            else:
                ttk.Entry(form, textvariable=self.vars[key], width=70).grid(row=i, column=1, sticky="we", padx=6, pady=5)
            if key == "output":
                ttk.Button(form, text="选择", command=self.choose_output).grid(row=i, column=2, padx=6, pady=5)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="核心创意").grid(row=len(rows), column=0, sticky="nw", padx=6, pady=5)
        self.premise_text = tk.Text(form, height=6, wrap="word")
        self.premise_text.grid(row=len(rows), column=1, columnspan=2, sticky="we", padx=6, pady=5)
        self.premise_text.insert("1.0", "男主在家族内乱后隐姓埋名，当了三年上门女婿。所有人都骂他废物，寿宴当天他身份曝光，龙腾集团跪迎少主归位，从此打脸赵家、前妻后悔、清算叶家旧账。")

        btns = ttk.Frame(gen)
        btns.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns, text="保存配置", command=self.save_cfg_from_ui).pack(side="left", padx=4)
        ttk.Button(btns, text="开始生成", command=self.start_generation).pack(side="left", padx=4)
        ttk.Button(btns, text="打开输出目录", command=self.open_output).pack(side="left", padx=4)

        log_frame = ttk.LabelFrame(gen, text="运行日志")
        log_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_text = tk.Text(log_frame, height=18, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

        # 配置页
        self.vars["text_base_url"] = self.v(text_cfg.get("base_url", ""))
        self.vars["text_api_key"] = self.v(text_cfg.get("api_key", ""))
        self.vars["text_model"] = self.v(text_cfg.get("model", ""))
        self.vars["text_temp"] = self.v(text_cfg.get("temperature", 0.8))
        self.vars["text_timeout"] = self.v(text_cfg.get("timeout", 180))

        self.config_section(cfg_tab, "文本模型（OpenAI-compatible /chat/completions）", [
            ("Base URL", "text_base_url", False),
            ("API Key", "text_api_key", True),
            ("Model", "text_model", False),
            ("Temperature", "text_temp", False),
            ("Timeout", "text_timeout", False),
        ], 0)
        ttk.Button(cfg_tab, text="保存模型配置到 config.local.json", command=self.save_cfg_from_ui).pack(anchor="w", padx=14, pady=10)
        ttk.Label(cfg_tab, text=f"配置文件：{CONFIG_PATH}\n注意：config.local.json 已加入 .gitignore，请不要提交或分享。", foreground="#666").pack(anchor="w", padx=14, pady=4)

    def config_section(self, parent, title, rows, idx):
        frame = ttk.LabelFrame(parent, text=title)
        frame.pack(fill="x", padx=8, pady=8)
        for i, (label, key, secret) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=5)
            ttk.Entry(frame, textvariable=self.vars[key], show="*" if secret else "", width=80).grid(row=i, column=1, sticky="we", padx=6, pady=5)
        frame.columnconfigure(1, weight=1)

    def choose_output(self):
        d = filedialog.askdirectory(initialdir=self.vars["output"].get() or str(Path.home()))
        if d:
            self.vars["output"].set(d)

    def log(self, msg: str):
        self.log_queue.put(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def drain_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
        except queue.Empty:
            pass
        self.after(200, self.drain_logs)

    def save_cfg_from_ui(self):
        try:
            cfg = {
                "text": {
                    "base_url": self.vars["text_base_url"].get().strip(),
                    "api_key": self.vars["text_api_key"].get().strip(),
                    "model": self.vars["text_model"].get().strip(),
                    "temperature": float(self.vars["text_temp"].get()),
                    "timeout": int(float(self.vars["text_timeout"].get())),
                },
                "app": {"default_output_dir": self.vars["output"].get().strip()},
            }
            save_config(cfg)
            self.cfg = cfg
            messagebox.showinfo("已保存", f"配置已保存到：\n{CONFIG_PATH}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def build_job(self) -> NovelJob:
        return NovelJob(
            title=self.vars["title"].get().strip(),
            channel=self.vars["channel"].get().strip(),
            genre=self.vars["genre"].get().strip(),
            premise=self.premise_text.get("1.0", "end").strip(),
            chapters=int(self.vars["chapters"].get()),
            words_per_chapter=int(self.vars["words"].get()),
            output_root=Path(self.vars["output"].get().strip()),
            author_name=self.vars["author"].get().strip() or "昨页",
        )

    def start_generation(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("正在运行", "已有任务正在运行，请等待完成。")
            return
        self.save_cfg_from_ui()
        try:
            job = self.build_job()
        except Exception as e:
            messagebox.showerror("参数错误", str(e))
            return
        self.worker = threading.Thread(target=self.run_worker, args=(job,), daemon=True)
        self.worker.start()

    def run_worker(self, job: NovelJob):
        try:
            text_cfg = self.cfg["text"]
            if not text_cfg.get("api_key"):
                raise RuntimeError("请先在模型配置里填写文本模型 API Key")
            text_client = OpenAICompatibleClient(text_cfg["base_url"], text_cfg["api_key"], text_cfg["model"], int(text_cfg.get("timeout", 180)))
            gen = NovelGenerator(text_client, float(text_cfg.get("temperature", 0.8)), self.log)
            path = gen.run(job)
            self.log(f"全部完成，输出目录：{path}")
            messagebox.showinfo("完成", f"小说已生成：\n{path}")
        except Exception as e:
            self.log(f"失败：{e}")
            messagebox.showerror("生成失败", str(e))

    def open_output(self):
        p = Path(self.vars["output"].get().strip())
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(str(p))


if __name__ == "__main__":
    App().mainloop()
