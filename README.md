# Financial Optimization — Project, Topic 4: Active Portfolio Management

Market-neutral long-short strategy on the 500 largest US stocks, 1995–2025: Barra-style risk model,
Grinold alphas from stock characteristics, and a monthly max-Sharpe portfolio solved with Gurobi.

## Run it
1. Python 3.12, `pip install -r requirements.txt`, plus a Gurobi license (academic is fine).
2. In the first code cell of `project_topic4.ipynb`, set `WRDS_USERNAME` to your WRDS username.
3. Run all cells: about 10 minutes. The first run also pulls about 3 minutes of WRDS data into `data/`.

## Files
| File | Content |
|---|---|
| `project_topic4.ipynb` | Whole pipeline, experiments and results (the demo deliverable) |
| `wrds_data.py` | WRDS queries and the parquet cache |
| `MktRf.csv` | Monthly market excess return and risk-free rate (Ken French), **in percent** |
| `data/` | *Not in git.* Parquet cache, rebuilt automatically; delete it to force a fresh pull |

**Data flow:** CRSP monthly comes from `monthly_returns.csv` (downloaded manually fron WRDS) if present, otherwise the same table is pulled with the API (identical rows). Either way it is cached as `data/crsp.parquet`, and the CSV is read only once.
CRSP daily returns (stocks ever in the universe only), Fama-French daily factors, Compustat annual,
the CCM link and the GICS history are always pulled with the API. Never commit raw CRSP/Compustat data:
the WRDS license forbids it and the repo is public.

## Method (notebook sections)
- **1–4** Data, point-in-time GICS sectors, universe (top 500 by cap; incumbents stay while rank ≤ 550), benchmarks
- **5** Characteristics: beta and residual vol from 252 daily returns, size; signals `mom`, `rev`, `gp`, `ag`
- **6** Risk model `V = X F Xᵀ + D` from monthly cross-sectional WLS regressions (10 sectors + styles)
- **7** Monthly Spearman ICs (raw and vs risk-model residuals)
- **8** Alpha = IC × residual vol × z
- **9** Gurobi: max α'w − κ·turnover s.t. risk budget, dollar-neutral, factor exposures within ±margin
- **10–13** Experiments: are the signals systematic, three risk treatments, turnover penalty, covariance estimators
- **14–15** Combination preview and summary

## Results so far (1995–2025, net of 10 bp costs, turnover penalty = cost)
| Long-short book | Net Sharpe | Beta | Alpha t-stat |
|---|---|---|---|
| Momentum (12-1) | 0.42 | −0.01 | 2.4 |
| Gross profitability | 0.48 | −0.02 | 2.8 |
| Asset growth | 0.44 | −0.01 | 2.4 |
| Short-term reversal | −0.02 | 0.08 | −0.7 |
| **Mom + gp + ag, equal weight** | **0.74** | −0.01 | 4.2 |
| Market (benchmark) | 0.61 | 1 | – |

* The signals are systematic. Unless they are added to the risk model as factors, their risk is
  underestimated 1.3–2.1×. Neutralizing them removes most of the alpha.
* The turnover penalty cuts turnover 3–6× and raises net Sharpe. Reversal only works before costs.
* Sector factors matter a lot. Extra covariance shrinkage did not help.

## Next steps
- One combined alpha (mom + gp + ag) optimized jointly instead of averaging books
- Sub-period and drawdown analysis of the final strategy, then the slides
