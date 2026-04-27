# lotto
抓取百度双色球数据  
使用盖尔·霍华德在《彩票中奖指南》叙述的方法计算中奖概率  
输出Excel  
  
Double Color Balls  
Using Gail Howard's methord to count the double color balls.

## Python 3

当前版本已重构为 Python 3 脚本，默认将结果写入项目内的 `data/output/data.xlsx`，并改为从东方财富彩票历史页抓取双色球数据。

当前项目结构：

```text
.
├── data/
│   ├── cache/
│   │   ├── history_cache.json
│   │   └── pipeline_state.json
│   ├── input/
│   └── output/
│       ├── data.xlsx
│       ├── sample_features.csv
│       └── ...
├── docs/
│   └── improvement-notes.md
├── lotto_app/
│   ├── cli.py
│   ├── fetcher.py
│   ├── analysis.py
│   ├── features.py
│   ├── rules.py
│   ├── backtest.py
│   ├── report.py
│   ├── patterns.py
│   ├── excel.py
│   └── state.py
├── tests/
│   ├── test_fetcher.py
│   ├── test_analysis.py
│   └── test_features_backtest.py
├── scripts/
│   └── run.sh
├── lotto.py
├── pyproject.toml
├── requirements.txt
├── run.sh
└── README.md
```

约定：

- `data/cache/` 存放抓取缓存和流水线状态
- `data/input/` 预留给规则配置和手工输入文件
- `data/output/` 存放 Excel 与各类 csv 导出
- `lotto_app/` 存放核心业务代码
- `tests/` 存放最小回归测试
- `scripts/` 存放执行脚本
- `docs/` 存放补充说明和历史整理文档
- 根目录 `run.sh` 只是兼容入口，实际转发到 `scripts/run.sh`
- `data/cache/history_cache.json` 缓存历史开奖数据，首次全量抓取，后续仅同步增量
- `data/cache/pipeline_state.json` 记录第一阶段导出的输入签名，数据和参数未变化时跳过重算
- `data/output/sample_features.csv` 是第一阶段生成的特征样本表
- `data/output/rule_effectiveness.csv` 是第一阶段生成的规则有效性报表
- `data/output/rule_grid_report.csv` 是多套规则参数的横向比较报表
- `data/output/rule_grid_summary.csv` 是多套规则参数的排序摘要报表
- `data/output/model_ranking.csv` 是基于简单 Logistic Regression 的最新一期号码排序结果
- `data/output/model_metrics.csv` 是模型在测试集上的 Top-K 评估结果
- `data/output/model_blue_ranking.csv` 是蓝球模型对最新一期的排序结果
- `data/output/model_blue_metrics.csv` 是蓝球模型在测试集上的评估结果
- `data/output/candidate_pools.csv` 是基于最新红蓝排序生成的候选池摘要
- `data/output/candidate_combinations.csv` 是加上基础约束后的红球候选组合
- `data/output/strategy_backtest.csv` 是基于测试期历史排序回放出来的策略回测摘要
- `lotto_app/patterns.py` 将趋势逆转、层叠、反向层叠、n倍底、旗式排列抽成可复用模式模块

首次初始化：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

日常运行：

```bash
source .venv/bin/activate
python lotto.py
```

可选参数：

```bash
python lotto.py --xlsx ./data/output/data.xlsx --draws 100
```

规则阈值调参示例：

```bash
python lotto.py \
  --omit-threshold 12 \
  --gap-ratio-threshold 1.8 \
  --heat-score-threshold 0.75 \
  --gap-cv-threshold 0.8
```

模式阈值调参示例：

```bash
python lotto.py \
  --trend-reverse-min-omit 19 \
  --pile-long-min 16 \
  --pile-mid-min 9 \
  --pile-short-min 4 \
  --flag-range-start-min 5 \
  --flag-range-start-max 7 \
  --flag-range-min-repeat 3
```

批量规则配置示例：

```json
{
  "configs": [
    { "name": "base", "omit_threshold": 10, "heat_score_threshold": 0.6 },
    { "name": "aggressive", "omit_threshold": 12, "heat_score_threshold": 0.75, "gap_cv_threshold": 0.8 }
  ]
}
```

```bash
python lotto.py --rule-config ./data/input/rule_configs.json
```

如需自定义批量对比摘要输出路径：

```bash
python lotto.py \
  --rule-config ./data/input/rule_configs.json \
  --rule-grid-summary-csv ./data/output/rule_grid_summary.csv
```

如需直接在命令行生成参数网格：

```bash
python lotto.py \
  --sweep-omit-thresholds 10,12,14 \
  --sweep-heat-score-thresholds 0.6,0.75 \
  --sweep-gap-cv-thresholds 0.5,0.8
```

第一阶段额外导出：

```bash
python lotto.py \
  --sample-csv ./data/output/sample_features.csv \
  --rule-report-csv ./data/output/rule_effectiveness.csv \
  --model-ranking-csv ./data/output/model_ranking.csv \
  --model-metrics-csv ./data/output/model_metrics.csv \
  --blue-model-ranking-csv ./data/output/model_blue_ranking.csv \
  --blue-model-metrics-csv ./data/output/model_blue_metrics.csv \
  --candidate-pools-csv ./data/output/candidate_pools.csv \
  --candidate-combinations-csv ./data/output/candidate_combinations.csv \
  --strategy-backtest-csv ./data/output/strategy_backtest.csv
```

固定注数策略示例：

```bash
python lotto.py \
  --candidate-combo-limit 20 \
  --strategy-start-bankroll 1000 \
  --strategy-ticket-cost 2 \
  --strategy-combo-ticket-count 5 \
  --strategy-blue-ticket-count 3
```

启用滚动时序回测参数：

```bash
python lotto.py \
  --rolling-min-train-draws 100 \
  --rolling-step 1
```

如果你不想每次手动激活虚拟环境，可以直接使用项目内脚本：

```bash
./run.sh
```

这个脚本会：

- 自动创建 `.venv`
- 自动激活虚拟环境
- 缺少依赖时自动安装 `requirements.txt`
- 运行 `lotto.py`

运行测试：

```bash
python3 -m unittest discover -s tests
```

如果你改了依赖并希望强制重新同步，可以执行：

```bash
./run.sh --sync-deps
```

说明：

- `--draws` 必须大于等于 `100`，因为现有统计逻辑固定依赖最近 100 期数据。
- `--full-history-draws 0` 表示特征和回测使用全量历史；非 0 时使用指定条数。
- 数据抓取现在依赖东方财富的历史开奖页；如果上游页面结构变化，脚本会直接报错退出。
- 历史开奖会缓存到 `data/cache/history_cache.json`；首次运行全量抓取，后续运行只抓取新期次。
- 第一阶段导出会根据缓存数据和滚动参数计算输入签名；如果历史数据和参数都没变化，则直接复用已有 csv，不重复回测和训练。
- 规则阈值参数也会写入第一阶段输入签名；调整阈值后会自动重建 `sample_features.csv / rule_effectiveness.csv / model_ranking.csv / model_metrics.csv`。
- `--rule-config` 中的多套参数也会进入第一阶段输入签名；配置集变化后会自动重建对比报表。
- `data/output/data.xlsx` 也会根据最近 `--draws` 期数据计算签名；最近期数据未变化时直接复用已有工作簿，不重复生成。
- Excel 中新增了 `原始数据` 工作表，用于保存最近 100 期原始开奖明细，便于人工核对。
- `sample_features.csv` 采用“每期、每号一行”的结构，并包含 `y_1 / y_3 / y_5` 标签。
- `sample_features.csv` 同时包含原有经验模式的触发标记，如 `is_trend_reverse / is_pile / is_re_pile / is_n_bottom / is_flag_range`。
- `sample_features.csv` 现在还包含多窗口频次特征：`freq_5 / freq_10 / freq_30 / freq_100 / freq_300 / freq_all`。
- `sample_features.csv` 还包含连续热度与遗漏波动特征：`heat_score / gap_stddev / gap_cv`。
- 经验模式特征现在支持通过 CLI 或 `--rule-config` 调整关键阈值，如趋势逆转最低遗漏值、层叠长/中/短区间下限、旗式排列起始区间与最少重复次数。
- `rule_effectiveness.csv` 同时输出训练/测试切分结果、滚动时序回测结果，以及规则参数摘要。
- `rule_grid_report.csv` 会把 `--rule-config` 中的每套参数展开成单独 `config_name`，便于横向比较规则表现。
- `rule_grid_summary.csv` 会基于 `lift_y1_test / rolling_lift_y1 / lift_y3_test / rolling_lift_y3` 生成排序摘要，方便优先筛选值得继续验证的规则配置。
- `model_ranking.csv` 输出当前模型对最新一个可标注期次的 33 个红球排序概率。
- `model_metrics.csv` 输出红球 Logistic 模型与简单遗漏/热度基线在测试期上的评估结果，当前默认使用 `Top-6 / Top-10`。
- `model_blue_ranking.csv` 输出当前模型对最新一个可标注期次的 16 个蓝球排序概率。
- `model_blue_metrics.csv` 输出蓝球 Logistic 模型与简单遗漏/热度基线在测试期上的评估结果，当前默认使用 `Top-1 / Top-3`。
- `candidate_pools.csv` 会基于最新一期红球/蓝球排序输出 `red_dan_pool / red_candidate_pool / red_kill_pool / blue_dan_pool / blue_candidate_pool / blue_kill_pool`，作为后续组合约束生成的输入。
- `candidate_combinations.csv` 会基于 `candidate_pools.csv` 和最新排序生成受约束的红球组合，当前默认要求：胆码命中不少于 2 个、奇偶比在 `2:4~4:2`、大小比在 `3:3~5:1`、至少覆盖 2 个三区、和值在 `70~150`，并附带建议蓝球池。
- `strategy_backtest.csv` 会基于测试期历史排序回放 `red_dan_pool / red_candidate_pool / red_kill_pool / blue_candidate_pool / red_combo_cover_4plus / red_combo_full_cover` 六类策略，并同时给出逐期结果和 summary 聚合结果。
- `strategy_backtest.csv` 里的随机基线使用超几何分布计算；其中 `red_candidate_pool` 的 success 定义为红球候选池覆盖下一期至少 `4` 个红球，`red_combo_cover_4plus` 的 success 定义为导出的候选组合里至少有 1 注命中 `4` 个红球。
- `strategy_backtest.csv` 现在还包含 `fixed_ticket_bundle`，会把每期前 `--strategy-combo-ticket-count` 个红球候选组合和前 `--strategy-blue-ticket-count` 个蓝球候选做笛卡尔配对，按每注 `--strategy-ticket-cost` 模拟固定注数策略，并输出 `stake_amount / payout_amount / net_profit / bankroll_after`。
- `fixed_ticket_bundle` 的奖金回放采用固定奖级近似值：`6+1=5000000`、`6+0=100000`、`5+1=3000`、`5+0或4+1=200`、`4+0或3+1=10`、`0/1/2+1=5`。这是为了做稳定的历史资金曲线，不等同于真实浮动头奖。
