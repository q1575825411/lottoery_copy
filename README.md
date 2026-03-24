# lotto
抓取百度双色球数据  
使用盖尔·霍华德在《彩票中奖指南》叙述的方法计算中奖概率  
输出Excel  
  
Double Color Balls  
Using Gail Howard's methord to count the double color balls.

## Python 3

当前版本已重构为 Python 3 脚本，默认将结果写入项目内的 `data/data.xlsx`，并改为从东方财富彩票历史页抓取双色球数据。

当前项目结构：

```text
.
├── data/
│   └── data.xlsx
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

- `data/` 存放运行输出和后续数据文件
- `lotto_app/` 存放核心业务代码
- `tests/` 存放最小回归测试
- `scripts/` 存放执行脚本
- 根目录 `run.sh` 只是兼容入口，实际转发到 `scripts/run.sh`
- `data/sample_features.csv` 是第一阶段生成的特征样本表
- `data/rule_effectiveness.csv` 是第一阶段生成的规则有效性报表
- `data/model_ranking.csv` 是基于简单 Logistic Regression 的最新一期号码排序结果
- `data/model_metrics.csv` 是模型在测试集上的 Top-K 评估结果
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
python lotto.py --xlsx ./data/data.xlsx --draws 100
```

第一阶段额外导出：

```bash
python lotto.py \
  --sample-csv ./data/sample_features.csv \
  --rule-report-csv ./data/rule_effectiveness.csv \
  --model-ranking-csv ./data/model_ranking.csv \
  --model-metrics-csv ./data/model_metrics.csv
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
python -m unittest discover -s tests
```

如果你改了依赖并希望强制重新同步，可以执行：

```bash
./run.sh --sync-deps
```

说明：

- `--draws` 必须大于等于 `100`，因为现有统计逻辑固定依赖最近 100 期数据。
- `--full-history-draws 0` 表示特征和回测使用全量历史；非 0 时使用指定条数。
- 数据抓取现在依赖东方财富的历史开奖页；如果上游页面结构变化，脚本会直接报错退出。
- Excel 中新增了 `原始数据` 工作表，用于保存最近 100 期原始开奖明细，便于人工核对。
- `sample_features.csv` 采用“每期、每号一行”的结构，并包含 `y_1 / y_3 / y_5` 标签。
- `sample_features.csv` 同时包含原有经验模式的触发标记，如 `is_trend_reverse / is_pile / is_re_pile / is_n_bottom / is_flag_range`。
- `sample_features.csv` 现在还包含多窗口频次特征：`freq_5 / freq_10 / freq_30 / freq_100 / freq_300 / freq_all`。
- `rule_effectiveness.csv` 同时输出训练/测试切分结果和滚动时序回测结果。
- `model_ranking.csv` 输出当前模型对最新一个可标注期次的 33 个红球排序概率。
- `model_metrics.csv` 输出模型在测试期上的 `Top-6 / Top-10` 平均命中表现。
