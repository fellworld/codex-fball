# 2026 FIFA World Cup Data & Prediction Project

面向 2026 年 FIFA 世界杯的赛事资料收集、数据分析与赛果预测项目。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest
```

需要抓取赔率快照时，先复制 `.env.example` 为 `.env`，并设置 `THE_ODDS_API_KEY`。

## 项目目标

1. 收集世界杯基础资料：参赛队、分组、赛程、场馆、开球时间、历史战绩。
2. 构建球队画像：世界排名、近期状态、进攻防守指标、球员可用性、赛程强度。
3. 预测比赛结果：胜/平/负概率、比分分布、小组出线概率、淘汰赛晋级概率、冠军概率。
4. 输出可读结果：数据表、图表、模型解释、赛前报告或交互式仪表盘。

## 已确认赛事背景

- 2026 年世界杯由加拿大、墨西哥、美国联合举办。
- 赛事扩军至 48 队。
- 小组赛为 12 个小组，每组 4 队。
- 共 104 场比赛。
- 官方赛程、分组、参赛队名单应以 FIFA 最新页面为准。

## 推荐数据模块

### 官方赛事数据

- 参赛队名单
- 小组与赛程
- 比赛日期、城市、场馆
- 开球时间
- 淘汰赛路径

优先来源：FIFA 官方页面。

### 球队实力数据

- FIFA Ranking
- Elo rating
- 近 10-20 场国家队比赛结果
- 进球、失球、净胜球
- 对手强度修正后的表现
- 大赛经验

可选来源：FIFA、World Football Elo Ratings、Kaggle/openfootball、football-data 数据集等。

### 球员与阵容数据

- 预选名单与最终名单
- 球员俱乐部、年龄、位置
- 伤病与停赛
- 俱乐部赛季表现

这个模块数据波动最大，适合在赛事临近时再接入。

## 预测方法路线

### MVP 模型

先做一个可解释的基础模型：

- 用 Elo 或 FIFA Ranking 作为球队实力基线。
- 加入主办国/主场洲际优势。
- 用 Poisson 分布预测双方进球数。
- 从比分矩阵推导胜平负概率。
- 用 Monte Carlo 模拟小组赛和淘汰赛。

### 进阶模型

- 加入近期状态权重。
- 加入球队攻防强度。
- 使用 xG、射门、控球、压迫等高级指标。
- 训练机器学习模型：Logistic Regression、Random Forest、XGBoost、Bayesian model。
- 对小组赛出线与冠军概率做多次仿真。

## 建议项目结构

```text
codex-fball/
  README.md
  data/
    raw/
    processed/
  notebooks/
  src/
    collectors/
    features/
    models/
    simulation/
    reports/
  outputs/
    charts/
    reports/
  tests/
```

## 第一阶段 MVP

1. 建立赛程、球队、分组三张基础表。
2. 接入一份球队评级数据。
3. 实现单场胜平负概率预测。
4. 实现小组赛积分规则与出线模拟。
5. 生成一份 Markdown 或 HTML 预测报告。

## 已整理数据

- `data/processed/groups.csv`: 2026 世界杯 12 个小组、48 支球队。
- `data/processed/group_stage_schedule_cst.csv`: 小组赛 72 场比赛时间表，包含来源 BST 时间与转换后的中国时间。
- `data/processed/source_notes.md`: 数据来源、时区转换和整理说明。
- `config/odds_bookmakers.csv`: 赔率采集候选品牌与市场配置。
- `docs/odds_collection_plan.md`: 赔率采集、市场字段、快照频率与合规说明。
- `src/collectors/odds_collector.py`: 授权 odds API 快照采集器骨架。
- `docs/team_squad_tactics_plan.md`: 球员俱乐部、主力判断、教练打法与进球倾向的数据方案。
- `src/collectors/fifa_squad_collector.py`: FIFA 官方最终名单 PDF 采集器骨架。
- `data/processed/team_tactical_profiles.csv`: 48 队战术画像模板。
- `data/processed/squad_players.csv`: FIFA 官方最终名单解析出的 1,248 名球员与俱乐部信息。
- `data/processed/team_coaches.csv`: 48 支球队主教练信息。
- `src/features/team_club_features.py`: 从球员俱乐部生成球队层面的俱乐部分布特征。
- `data/processed/team_strength_ratings.csv`: 基于俱乐部分布的第一版球队强度评分。
- `data/processed/match_prediction_inputs.csv`: 72 场小组赛的第一版预测输入表。
- `data/processed/manual_team_ratings.csv`: FIFA 排名、Elo、人工攻防修正等后续评分输入模板。
- `docs/prediction_framework.md`: 预测框架、当前评分口径和后续模型路线。
- `src/features/odds_implied_probabilities.py`: 将赔率转换为去水后的市场隐含概率。
- `config/team_aliases.csv`: 赛程常用队名与 FIFA 官方名单队名的别名映射。
- `outputs/reports/prematch/index.md`: 72 场小组赛赛前报告索引。
- `src/reports/generate_prematch_reports.py`: 生成每场比赛的 Markdown 赛前报告。
- `data/processed/team_form_ratings.csv`: FIFA/Elo/近期状态数据模板。
- `data/processed/team_phase_ratings.csv`: 进攻、防守、门将、定位球、转换能力分项模板。
- `data/processed/expected_lineups.csv`: 预计主力、伤停、停赛、出场时间模板。
- `data/processed/match_context.csv`: 城市、场馆、天气、休息天数、旅途、主场优势模板。
- `data/processed/model_match_inputs.csv`: Poisson 模型输入表，含双方预期进球。
- `data/processed/match_simulation_summary.csv`: 单场胜平负、大小球、最可能比分模拟结果。
- `data/processed/match_score_probabilities.csv`: 每场比赛的比分概率矩阵。
- `data/processed/group_stage_simulation_summary.csv`: 小组排名、出线概率模拟结果。
- `docs/simulation_model.md`: 当前模拟模型说明与升级路线。
- `data/processed/public_elo_ratings.csv`: World Football Elo Ratings 公开 Elo 数据。
- `data/processed/fifa_ranking_metadata.json`: FIFA 官方排名页元数据；完整 FIFA 排名表未暴露时，模型使用 Elo rank proxy 并在字段中标明。
- `data/processed/team_form_features.csv`: 最近 20 场国家队赛果特征。
- `data/processed/team_power_ratings.csv`: Elo、俱乐部质量、近期状态、FIFA-rank proxy 融合后的综合评分。
- `src/collectors/public_football_data.py`: 拉取公开赛果、Elo、FIFA ranking metadata。
- `src/collectors/match_context_collector.py`: 从公开世界杯赛程 JSON 生成场馆/主场环境表。
- `src/features/team_form_features.py`: 从公开赛果生成近期状态特征。
- `src/features/team_power_ratings.py`: 生成综合评分与攻防分项。

## 关键规则

小组赛排名通常需要处理：

- 积分
- 净胜球
- 进球数
- 相互比赛结果
- 公平竞赛分
- 抽签或官方规则中的最终判定

实现时应把规则做成独立模块，避免和模型逻辑混在一起。

## 下一步

建议先选择一个交付形态：

- Python 数据分析项目：适合快速建模和报告。
- Streamlit 仪表盘：适合交互式展示预测结果。
- Web App：适合做成完整产品。
- Notebook 项目：适合探索和讲解模型过程。

## 本地网页控制台

推荐用启动器打开项目自带的轻量网页界面：

```powershell
.\scripts\start_web_console.ps1
```

也可以直接双击项目根目录下的 `start_web_console.cmd`。

如果想在当前终端前台运行，方便查看日志：

```powershell
python src/web_console.py
```

然后打开 http://127.0.0.1:8765。

注意：这是本机临时服务。电脑重启、终端关闭、Python 进程退出后，网页会显示连接失败；重新运行启动器即可恢复。

控制台支持：

- 浏览 `src`、`data/processed`、`outputs/reports`、`docs`、`config` 和 `tests`。
- 将 CSV 以表格预览，将 Markdown 报告转成网页预览，将代码/配置文件保留格式展示。
- 从网页运行白名单流程：构建模型输入、模拟单场比分、模拟小组出线、生成赛前报告、运行测试。
