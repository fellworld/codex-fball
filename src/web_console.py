"""本地网页控制台：浏览项目输出，并安全运行固定流程。"""

from __future__ import annotations

import csv
import html
import json
import mimetypes
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

VISIBLE_ROOTS = ("src", "data/processed", "outputs/reports", "docs", "config", "tests")
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".ps1",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
MAX_TEXT_BYTES = 700_000


@dataclass(frozen=True)
class ConsoleCommand:
    title: str
    description: str
    argv: tuple[str, ...]
    outputs: tuple[str, ...]


COMMANDS: dict[str, ConsoleCommand] = {
    "build-model-inputs": ConsoleCommand(
        title="构建模型输入",
        description="根据评分、战术画像和比赛环境，重新生成模型可用的预期进球输入表。",
        argv=(sys.executable, "-m", "features.model_input_builder"),
        outputs=("data/processed/model_match_inputs.csv",),
    ),
    "simulate-matches": ConsoleCommand(
        title="模拟单场比分",
        description="运行 Poisson 比分模型，输出胜/平/负概率和具体比分概率矩阵。",
        argv=(sys.executable, "-m", "simulation.poisson_match_simulator"),
        outputs=(
            "data/processed/match_simulation_summary.csv",
            "data/processed/match_score_probabilities.csv",
        ),
    ),
    "simulate-robust-matches": ConsoleCommand(
        title="Robust match simulation",
        description="Run uncertainty-aware Poisson mixtures and write robust score probabilities.",
        argv=(sys.executable, "-m", "simulation.robust_match_simulator"),
        outputs=(
            "data/processed/match_robust_simulation_summary.csv",
            "data/processed/match_robust_score_probabilities.csv",
            "data/processed/team_rating_uncertainty.csv",
        ),
    ),
    "simulate-groups": ConsoleCommand(
        title="模拟小组出线",
        description="运行 Monte Carlo 小组赛模拟，输出各队小组名次和出线概率。",
        argv=(sys.executable, "-m", "simulation.group_stage_simulator"),
        outputs=("data/processed/group_stage_simulation_summary.csv",),
    ),
    "generate-reports": ConsoleCommand(
        title="生成赛前报告",
        description="重新生成 72 场小组赛的 Markdown 赛前报告和索引。",
        argv=(sys.executable, "-m", "reports.generate_prematch_reports"),
        outputs=("outputs/reports/prematch/index.md",),
    ),
    "update-match-intelligence": ConsoleCommand(
        title="更新赛前情报",
        description="只刷新 1-8 场 Markdown 里的首发、伤停、战术标签、赔率和去水市场概率。",
        argv=(sys.executable, "-m", "reports.inject_match_intelligence"),
        outputs=(
            "data/processed/pre_match_intelligence_1_8.json",
            "outputs/reports/prematch/01-mexico-vs-south-africa.md",
        ),
    ),
    "full-refresh": ConsoleCommand(
        title="完整刷新：模型 + 模拟 + 报告",
        description="按顺序构建模型输入、模拟单场比分、模拟小组出线，并生成赛前报告及赛前情报。",
        argv=(sys.executable, "-m", "pipelines.full_refresh"),
        outputs=(
            "data/processed/model_match_inputs.csv",
            "data/processed/match_simulation_summary.csv",
            "data/processed/group_stage_simulation_summary.csv",
            "outputs/reports/prematch/index.md",
        ),
    ),
    "evaluate-market-recommendations": ConsoleCommand(
        title="结算盘口推荐",
        description="根据已录入赛果结算亚洲盘和大小球推荐，并生成盘口回测汇总。",
        argv=(sys.executable, "-m", "reports.evaluate_market_recommendations"),
        outputs=(
            "data/processed/recommendation_settlement.csv",
            "data/processed/market_backtest_summary.csv",
        ),
    ),
    "score-market-candidates": ConsoleCommand(
        title="评分盘口候选",
        description="按新策略给截图盘口打 A/B/C 分层，加入市场一致性、低比分密度和打穿风险过滤。",
        argv=(sys.executable, "-m", "reports.score_market_candidates"),
        outputs=("data/processed/market_candidate_scores.csv",),
    ),
    "backtest-strategy-tiers": ConsoleCommand(
        title="回测策略分层",
        description="用已完赛赛果回放 A/B/C 盘口策略，检查各层命中率和净值。",
        argv=(sys.executable, "-m", "reports.backtest_strategy_tiers"),
        outputs=(
            "data/processed/strategy_tier_backtest.csv",
            "data/processed/strategy_tier_backtest_summary.csv",
        ),
    ),
    "evaluate-probability-calibration": ConsoleCommand(
        title="Probability calibration",
        description="Evaluate Brier score and log loss for result and total probabilities.",
        argv=(sys.executable, "-m", "reports.evaluate_probability_calibration"),
        outputs=("data/processed/probability_calibration_report.csv",),
    ),
    "pytest": ConsoleCommand(
        title="运行测试",
        description="运行项目测试套件。",
        argv=(sys.executable, "-m", "pytest"),
        outputs=(),
    ),
}


def relative_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def resolve_project_path(raw_path: str) -> Path:
    candidate = (PROJECT_ROOT / raw_path).resolve()
    if candidate == PROJECT_ROOT or PROJECT_ROOT in candidate.parents:
        return candidate
    raise ValueError("路径超出项目目录，已拒绝访问。")


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".md":
        return "markdown"
    if suffix == ".json":
        return "json"
    if suffix in {".py", ".ps1", ".toml", ".yml", ".yaml", ".txt"}:
        return "code"
    return "binary"


def safe_read_text(path: Path) -> str:
    if path.stat().st_size > MAX_TEXT_BYTES:
        return f"文件超过 {MAX_TEXT_BYTES:,} 字节，网页内暂不展开。请从文件树中直接打开。"
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv_preview(path: Path, limit: int = 100) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for idx, row in enumerate(reader):
            if idx >= limit:
                break
            rows.append(row)
        return {
            "columns": reader.fieldnames or [],
            "rows": rows,
            "previewLimit": limit,
        }


def list_visible_files() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for root in VISIBLE_ROOTS:
        root_path = resolve_project_path(root)
        if not root_path.exists():
            continue
        for path in sorted(root_path.rglob("*")):
            if path.is_dir():
                continue
            if "__pycache__" in path.parts or path.suffix.lower() == ".pyc":
                continue
            rel = relative_path(path)
            items.append(
                {
                    "path": rel,
                    "name": path.name,
                    "kind": file_kind(path),
                    "size": path.stat().st_size,
                    "mtime": path.stat().st_mtime,
                }
            )
    return items


def project_overview() -> dict[str, Any]:
    files = list_visible_files()
    counts: dict[str, int] = {}
    for item in files:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1

    highlights = [
        "data/processed/match_simulation_summary.csv",
        "data/processed/group_stage_simulation_summary.csv",
        "data/processed/team_power_ratings.csv",
        "outputs/reports/prematch/index.md",
        "docs/simulation_model.md",
        "src/simulation/poisson_match_simulator.py",
    ]
    return {
        "name": "codex-fball",
        "root": str(PROJECT_ROOT),
        "fileCount": len(files),
        "counts": counts,
        "highlights": [path for path in highlights if resolve_project_path(path).exists()],
        "commands": {
            key: {
                "title": command.title,
                "description": command.description,
                "outputs": command.outputs,
            }
            for key, command in COMMANDS.items()
        },
    }


def run_command(command_key: str) -> dict[str, Any]:
    command = COMMANDS.get(command_key)
    if command is None:
        raise ValueError("未知命令。")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    started = time.time()
    completed = subprocess.run(
        command.argv,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return {
        "command": command_key,
        "title": command.title,
        "argv": list(command.argv),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsedSeconds": round(time.time() - started, 2),
        "outputs": command.outputs,
    }


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>codex-fball 本地控制台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7f2;
      --panel: #ffffff;
      --ink: #172126;
      --muted: #607079;
      --line: #d9e0d6;
      --accent: #126a4a;
      --accent-2: #0d4f8b;
      --code: #111827;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: end;
      padding: 20px 24px 16px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfa;
    }
    h1 { margin: 0; font-size: 24px; line-height: 1.15; font-weight: 760; }
    .sub { margin-top: 6px; color: var(--muted); max-width: 840px; }
    .root {
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 12px;
      text-align: right;
      overflow-wrap: anywhere;
    }
    main {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr) 360px;
      height: calc(100vh - 90px);
      min-height: 620px;
    }
    aside, section, .runner { min-width: 0; overflow: auto; }
    aside {
      border-right: 1px solid var(--line);
      background: #fbfcfa;
      padding: 16px;
    }
    section { padding: 18px 20px 28px; }
    .runner {
      border-left: 1px solid var(--line);
      background: #fbfcfa;
      padding: 16px;
    }
    .toolbar { display: grid; gap: 10px; margin-bottom: 14px; }
    input, select {
      width: 100%;
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--ink);
      padding: 0 10px;
      font: inherit;
    }
    button {
      border: 1px solid #abc3b7;
      border-radius: 6px;
      background: #eef6f1;
      color: var(--accent);
      min-height: 34px;
      padding: 7px 10px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }
    button:hover { background: #e3f0e9; }
    button:disabled { cursor: wait; opacity: .7; }
    .stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .stat {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 10px;
    }
    .stat b { display: block; font-size: 20px; line-height: 1.1; }
    .stat span { color: var(--muted); font-size: 12px; }
    .file-list { display: grid; gap: 4px; }
    .file-item {
      width: 100%;
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px;
      align-items: center;
      border: 0;
      background: transparent;
      color: var(--ink);
      text-align: left;
      padding: 7px 8px;
      min-height: 32px;
      font-weight: 500;
    }
    .file-item:hover, .file-item.active { background: #edf2ea; }
    .badge {
      border-radius: 999px;
      padding: 2px 7px;
      background: #e9edf3;
      color: #415163;
      font-size: 11px;
      text-transform: uppercase;
    }
    .path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .viewer-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: start;
      margin-bottom: 14px;
    }
    .viewer-title {
      margin: 0;
      font-size: 18px;
      overflow-wrap: anywhere;
    }
    .meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      overflow: hidden;
    }
    pre {
      margin: 0;
      padding: 16px;
      overflow: auto;
      color: #e5e7eb;
      background: var(--code);
      font: 12px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace;
      tab-size: 2;
    }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      max-width: 260px;
      overflow-wrap: anywhere;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f0f4ee;
      font-weight: 700;
    }
    .markdown { padding: 18px 22px; max-width: 960px; }
    .markdown h1, .markdown h2, .markdown h3 { line-height: 1.2; }
    .markdown code {
      padding: 2px 4px;
      border-radius: 4px;
      background: #eef1ea;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    .cmd {
      display: grid;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
      margin-bottom: 10px;
    }
    .cmd-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-weight: 750;
    }
    .cmd p { margin: 0; color: var(--muted); font-size: 12px; }
    .outputs { display: flex; flex-wrap: wrap; gap: 6px; }
    .output-link {
      border: 0;
      min-height: 24px;
      padding: 3px 7px;
      color: var(--accent-2);
      background: #edf3f8;
      font-size: 11px;
      font-weight: 650;
    }
    .log-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin: 18px 0 8px;
      font-weight: 750;
    }
    .empty { padding: 28px; color: var(--muted); text-align: center; }
    @media (max-width: 1080px) {
      main { grid-template-columns: 280px minmax(0, 1fr); height: auto; }
      .runner { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--line); }
    }
    @media (max-width: 760px) {
      header { grid-template-columns: 1fr; }
      .root { text-align: left; }
      main { grid-template-columns: 1fr; }
      aside, .runner { border: 0; border-bottom: 1px solid var(--line); max-height: 420px; }
      .viewer-head { grid-template-columns: 1fr; }
      .stats { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>codex-fball 本地控制台</h1>
      <div class="sub">浏览代码、数据、报告，并从网页触发已白名单的预测流程。</div>
    </div>
    <div class="root" id="projectRoot"></div>
  </header>
  <main>
    <aside>
      <div class="toolbar">
        <input id="search" placeholder="搜索文件、球队、报告...">
        <select id="kindFilter">
          <option value="">全部类型</option>
          <option value="csv">CSV 表格</option>
          <option value="markdown">Markdown 文档</option>
          <option value="code">代码/配置</option>
          <option value="json">JSON</option>
        </select>
      </div>
      <div class="stats" id="stats"></div>
      <div class="file-list" id="fileList"></div>
    </aside>
    <section>
      <div class="viewer-head">
        <div>
          <h2 class="viewer-title" id="viewerTitle">选择一个文件</h2>
          <div class="meta" id="viewerMeta">CSV 会以表格显示，Markdown 会转成网页预览，代码会保持格式。</div>
        </div>
        <button id="refreshButton">刷新列表</button>
      </div>
      <div class="panel" id="viewer"><div class="empty">从左侧选择一个文件开始。</div></div>
    </section>
    <div class="runner">
      <h2 class="viewer-title">运行入口</h2>
      <div class="meta" style="margin-bottom: 12px;">只开放固定命令，避免网页误执行任意命令行。</div>
      <div id="commands"></div>
      <div class="log-head">
        <span>运行日志</span>
        <span id="runStatus" class="meta"></span>
      </div>
      <div class="panel"><pre id="runLog">尚未运行命令。</pre></div>
    </div>
  </main>
  <script>
    const state = {overview: null, files: [], selectedPath: ""};
    const kindLabels = {
      binary: "二进制",
      code: "代码",
      csv: "表格",
      json: "JSON",
      markdown: "文档",
    };
    const columnLabels = {
      advance_probability: "出线概率",
      avg_goals_against: "场均失球",
      avg_goals_for: "场均进球",
      captured_probability_mass: "已覆盖概率质量",
      club_quality_rating: "俱乐部质量评分",
      club_quality_tier: "俱乐部质量档位",
      date_china: "中国日期",
      draw_probability: "平局概率",
      elo_rating: "Elo 评分",
      finish_1_probability: "小组第 1 概率",
      finish_2_probability: "小组第 2 概率",
      finish_3_probability: "小组第 3 概率",
      finish_4_probability: "小组第 4 概率",
      goals_a: "A 队进球",
      goals_b: "B 队进球",
      group: "小组",
      group_win_probability: "小组头名概率",
      initial_favorite: "初始优势方",
      initial_total_goals_lean: "初始大小球倾向",
      iterations: "模拟次数",
      most_likely_score: "最可能比分",
      most_likely_score_probability: "最可能比分概率",
      notes: "说明",
      over_2_5_probability: "大于 2.5 球概率",
      power_rating: "综合评分",
      probability: "概率",
      recent_draws: "近期平局",
      recent_losses: "近期负场",
      recent_wins: "近期胜场",
      score: "比分",
      source_order: "比赛序号",
      team: "球队",
      team_a: "A 队",
      team_a_canonical: "A 队标准名",
      team_a_expected_goals: "A 队预期进球",
      team_a_power_rating: "A 队综合评分",
      team_a_win_probability: "A 队胜率",
      team_b: "B 队",
      team_b_canonical: "B 队标准名",
      team_b_expected_goals: "B 队预期进球",
      team_b_power_rating: "B 队综合评分",
      team_b_win_probability: "B 队胜率",
      time_china: "中国时间",
      total_expected_goals: "总预期进球",
      under_2_5_probability: "小于等于 2.5 球概率",
    };
    const markdownTranslations = [
      [/^# Prematch Report Index$/gm, "# 赛前报告索引"],
      [/^## Team Snapshot$/gm, "## 球队快照"],
      [/^## Current Read$/gm, "## 当前解读"],
      [/^## Data Still Needed$/gm, "## 待补充数据"],
      [/- Group:/g, "- 小组:"],
      [/- China time:/g, "- 中国时间:"],
      [/- Initial favorite:/g, "- 初始优势方:"],
      [/- Initial total-goals lean:/g, "- 初始大小球倾向:"],
      [/- Club-quality rating gap:/g, "- 俱乐部质量评分差:"],
      [/- Simulated win\\/draw\\/loss:/g, "- 模拟胜/平/负:"],
      [/- Simulated over 2\\.5:/g, "- 模拟大于 2.5 球:"],
      [/- Most likely score:/g, "- 最可能比分:"],
      [/This is a model preview using public Elo, recent results, and official squad club affiliations\\. Treat it as a structured preview until odds, lineups, and injuries are complete\\./g, "这是一个模型预览，使用公开 Elo、近期赛果和官方名单中的俱乐部归属生成。在赔率、首发和伤停信息补齐前，请把它视为结构化赛前参考。"],
      [/- Expected starting XI/g, "- 预计首发阵容"],
      [/- Injuries and suspensions/g, "- 伤病与停赛"],
      [/- Tactical style labels/g, "- 战术风格标签"],
      [/- Opening and latest bookmaker odds/g, "- 初盘和最新机构赔率"],
      [/- Market-implied probabilities after removing overround/g, "- 去除水位后的市场隐含概率"],
      [/\\| Team \\| Club rating \\| Power \\| Elo \\| Recent W-D-L \\| GF\\/GA \\| Tier \\| Head coach \\| Big-five players \\| Domestic players \\| Top clubs \\|/g, "| 球队 | 俱乐部评分 | 综合评分 | Elo | 近期胜平负 | 进/失球 | 档位 | 主教练 | 五大联赛球员 | 国内联赛球员 | 主要俱乐部 |"],
    ];
    const $ = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
    function formatBytes(bytes) {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }
    function kindLabel(kind) {
      return kindLabels[kind] || kind;
    }
    function columnLabel(column) {
      return columnLabels[column] || column;
    }
    function localizeMarkdown(md) {
      return markdownTranslations.reduce((text, [pattern, replacement]) => {
        return text.replace(pattern, replacement);
      }, String(md));
    }
    function simpleMarkdown(md) {
      const lines = String(md).split(/\\r?\\n/);
      let output = "";
      let inList = false;
      let inCode = false;
      let code = [];
      const closeList = () => { if (inList) { output += "</ul>"; inList = false; } };
      for (const line of lines) {
        if (line.startsWith("```")) {
          if (inCode) {
            output += `<pre><code>${escapeHtml(code.join("\\n"))}</code></pre>`;
            code = [];
            inCode = false;
          } else {
            closeList();
            inCode = true;
          }
          continue;
        }
        if (inCode) { code.push(line); continue; }
        if (/^###\\s+/.test(line)) {
          closeList(); output += `<h3>${escapeHtml(line.replace(/^###\\s+/, ""))}</h3>`;
        } else if (/^##\\s+/.test(line)) {
          closeList(); output += `<h2>${escapeHtml(line.replace(/^##\\s+/, ""))}</h2>`;
        } else if (/^#\\s+/.test(line)) {
          closeList(); output += `<h1>${escapeHtml(line.replace(/^#\\s+/, ""))}</h1>`;
        } else if (/^-\\s+/.test(line)) {
          if (!inList) { output += "<ul>"; inList = true; }
          output += `<li>${escapeHtml(line.replace(/^-\\s+/, ""))}</li>`;
        } else if (line.trim() === "") {
          closeList();
        } else {
          closeList(); output += `<p>${escapeHtml(line)}</p>`;
        }
      }
      closeList();
      return output;
    }
    async function getJson(url, options) {
      const response = await fetch(url, options);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || response.statusText);
      return payload;
    }
    function renderStats() {
      const counts = state.overview.counts || {};
      $("stats").innerHTML = [
        ["文件", state.overview.fileCount],
        ["CSV", counts.csv || 0],
        ["报告", counts.markdown || 0],
      ].map(([label, value]) => `<div class="stat"><b>${value}</b><span>${label}</span></div>`).join("");
    }
    function renderFiles() {
      const q = $("search").value.trim().toLowerCase();
      const kind = $("kindFilter").value;
      const files = state.files.filter((file) => {
        return (!q || file.path.toLowerCase().includes(q)) && (!kind || file.kind === kind);
      });
      $("fileList").innerHTML = files.map((file) => `
        <button class="file-item ${file.path === state.selectedPath ? "active" : ""}" data-path="${escapeHtml(file.path)}" title="${escapeHtml(file.path)}">
          <span class="badge">${escapeHtml(kindLabel(file.kind))}</span>
          <span class="path">${escapeHtml(file.path)}</span>
        </button>
      `).join("") || `<div class="empty">没有匹配文件。</div>`;
      document.querySelectorAll(".file-item").forEach((button) => {
        button.addEventListener("click", () => openFile(button.dataset.path));
      });
    }
    function renderCommands() {
      const commands = state.overview.commands;
      $("commands").innerHTML = Object.entries(commands).map(([key, command]) => `
        <div class="cmd">
          <div class="cmd-title">
            <span>${escapeHtml(command.title)}</span>
            <button data-command="${escapeHtml(key)}">运行</button>
          </div>
          <p>${escapeHtml(command.description)}</p>
          <div class="outputs">
            ${(command.outputs || []).map((path) => `<button class="output-link" data-path="${escapeHtml(path)}">${escapeHtml(path.split("/").at(-1))}</button>`).join("")}
          </div>
        </div>
      `).join("");
      document.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => runCommand(button.dataset.command));
      });
      document.querySelectorAll(".output-link").forEach((button) => {
        button.addEventListener("click", () => openFile(button.dataset.path));
      });
    }
    async function loadOverview() {
      const [overview, files] = await Promise.all([getJson("/api/overview"), getJson("/api/files")]);
      state.overview = overview;
      state.files = files.files;
      $("projectRoot").textContent = overview.root;
      renderStats();
      renderFiles();
      renderCommands();
      if (!state.selectedPath && overview.highlights.length) openFile(overview.highlights[0]);
    }
    async function openFile(path) {
      state.selectedPath = path;
      renderFiles();
      $("viewerTitle").textContent = path;
      $("viewerMeta").textContent = "加载中...";
      $("viewer").innerHTML = `<div class="empty">正在读取 ${escapeHtml(path)}</div>`;
      try {
        const file = await getJson(`/api/file?path=${encodeURIComponent(path)}`);
        $("viewerMeta").textContent = `${kindLabel(file.kind)} · ${formatBytes(file.size)} · ${new Date(file.mtime * 1000).toLocaleString()}`;
        if (file.kind === "csv") {
          const cols = file.preview.columns;
          $("viewer").innerHTML = `
            <div style="overflow:auto; max-height: calc(100vh - 180px);">
              <table>
                <thead><tr>${cols.map((col) => `<th title="${escapeHtml(col)}">${escapeHtml(columnLabel(col))}</th>`).join("")}</tr></thead>
                <tbody>${file.preview.rows.map((row) => `<tr>${cols.map((col) => `<td>${escapeHtml(row[col])}</td>`).join("")}</tr>`).join("")}</tbody>
              </table>
            </div>`;
        } else if (file.kind === "markdown") {
          $("viewer").innerHTML = `<div class="markdown">${simpleMarkdown(localizeMarkdown(file.content))}</div>`;
        } else {
          $("viewer").innerHTML = `<pre>${escapeHtml(file.content)}</pre>`;
        }
      } catch (error) {
        $("viewerMeta").textContent = "读取失败";
        $("viewer").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      }
    }
    async function runCommand(commandKey) {
      document.querySelectorAll("[data-command]").forEach((item) => item.disabled = true);
      $("runStatus").textContent = "运行中...";
      $("runLog").textContent = `正在运行：${commandKey}...\\n`;
      try {
        const result = await getJson("/api/run", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({command: commandKey}),
        });
        $("runStatus").textContent = `退出码 ${result.returncode} · ${result.elapsedSeconds}s`;
        $("runLog").textContent = [
          `$ ${result.argv.join(" ")}`,
          "",
          "标准输出：",
          result.stdout || "（空）",
          "",
          "错误输出：",
          result.stderr || "（空）",
        ].join("\\n");
        await loadOverview();
      } catch (error) {
        $("runStatus").textContent = "运行失败";
        $("runLog").textContent = error.message;
      } finally {
        document.querySelectorAll("[data-command]").forEach((item) => item.disabled = false);
      }
    }
    $("search").addEventListener("input", renderFiles);
    $("kindFilter").addEventListener("change", renderFiles);
    $("refreshButton").addEventListener("click", loadOverview);
    loadOverview().catch((error) => {
      $("viewer").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    });
  </script>
</body>
</html>
"""


class ConsoleRequestHandler(BaseHTTPRequestHandler):
    server_version = "codex-fball-console/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, content: str) -> None:
        body = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self.send_json({"error": message}, status=status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self.send_html(HTML_PAGE)
            elif parsed.path == "/api/overview":
                self.send_json(project_overview())
            elif parsed.path == "/api/files":
                self.send_json({"files": list_visible_files()})
            elif parsed.path == "/api/file":
                params = parse_qs(parsed.query)
                raw_path = params.get("path", [""])[0]
                self.send_json(self.file_payload(raw_path))
            else:
                self.send_error_json("未找到请求的页面。", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except FileNotFoundError:
            self.send_error_json("未找到文件。", HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - defensive request boundary
            self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error_json("未找到请求的接口。", HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            command_key = str(payload.get("command", ""))
            self.send_json(run_command(command_key))
        except subprocess.TimeoutExpired:
            self.send_error_json("命令运行超时。", HTTPStatus.REQUEST_TIMEOUT)
        except ValueError as exc:
            self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive request boundary
            self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def file_payload(self, raw_path: str) -> dict[str, Any]:
        path = resolve_project_path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(raw_path)
        kind = file_kind(path)
        payload: dict[str, Any] = {
            "path": relative_path(path),
            "name": path.name,
            "kind": kind,
            "size": path.stat().st_size,
            "mtime": path.stat().st_mtime,
            "mime": mimetypes.guess_type(path.name)[0],
        }
        if kind == "csv":
            payload["preview"] = read_csv_preview(path)
            payload["content"] = safe_read_text(path)
        elif path.suffix.lower() in TEXT_SUFFIXES:
            payload["content"] = safe_read_text(path)
        else:
            payload["content"] = html.escape("二进制文件暂不支持网页预览。")
        return payload


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="启动 codex-fball 本地网页控制台。")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ConsoleRequestHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"codex-fball 本地控制台已启动：{url}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止控制台。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
