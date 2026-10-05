# Financial Optimization — Project, Topic 4: Active Portfolio Management

Market-neutral long-short strategy on the 500 largest US stocks, 1995–2025: Barra-style risk model,
Grinold alphas from stock characteristics, and a monthly max-Sharpe portfolio solved with Gurobi.

## Run it
1. Python 3.12, `pip install -r requirements.txt`, plus a Gurobi license (academic is fine).
2. In the first code cell of `project_demo.ipynb`, set `WRDS_USERNAME` to your WRDS username.
3. Run all cells: about 10 minutes. The first run also pulls about 3 minutes of WRDS data into `data/`.

## Files
| File | Content |
|---|---|
| `project_demo.ipynb` | Whole pipeline, experiments and results (the demo deliverable) |
| `wrds_data.py` | WRDS queries and the parquet cache |
| `MktRf.csv` | Monthly market excess return and risk-free rate (Ken French), **in percent** |
| `data/` | *Not in git.* Parquet cache, rebuilt automatically; delete it to force a fresh pull |

**Data flow:** CRSP monthly comes from `monthly_returns.csv` (downloaded manually from WRDS) if present, otherwise the same table is pulled with the API (identical rows). Either way it is cached as `data/crsp.parquet`, and the CSV is read only once.
CRSP daily returns (stocks ever in the universe only), Fama-French daily factors, Compustat annual,
the CCM link and the GICS history are always pulled with the API.

## Method (notebook sections)
- **1–4** Data, point-in-time GICS sectors, universe (top 500 by cap; incumbents stay while rank ≤ 550), benchmarks
- **5** Characteristics: beta and residual vol from 252 daily returns, size; signals `mom`, `rev`, `gp`, `ag`
- **6** Risk model `V = X F Xᵀ + D` from monthly cross-sectional WLS regressions (10 sectors + styles)
- **7** Monthly Spearman ICs (raw and vs risk-model residuals)
- **8** Alpha = IC × residual vol × z
- **9** Gurobi: max α'w − κ·turnover s.t. risk budget, dollar-neutral, factor exposures within ±margin
- **10–13** Experiments: are the signals systematic, three risk treatments, turnover penalty, covariance estimators
- **14–15** Combination preview and summary
- **16** Final comparison on daily returns: averaged books, plain sum of Grinold alphas, plain sum with
  the cross-sectional mean specific vol

## Results (1995–2025, net of 10 bp costs, turnover penalty = cost)
**Final books** (section 16, daily returns). Return / risk uses total returns; the Sharpe ratio subtracts
the risk-free rate (2.4% a year on average).

| Book | Return / risk (total returns) | Sharpe (excess of RF) | Ann. return | Ann. vol | Max drawdown |
|---|---|---|---|---|---|
| Market (benchmark) | 0.66 | 0.53 | 12.5% | 19.0% | −55% |
| **Averaged books (mom, gp, ag)** | **1.43** | **0.76** | 5.1% | 3.6% | −6% |
| Plain sum of Grinold alphas | 1.12 | 0.72 | 6.6% | 5.9% | −19% |
| Plain sum, cross-sectional mean σ | 1.20 | 0.80 | 7.0% | 5.9% | −14% |

**Return / vol on total returns** (daily returns, RF not subtracted; mean / std × √252)

| Book | Return / vol | Ann. return | Ann. vol | Max drawdown | Return / vol 1995–2004 | Return / vol 2005–2014 | Return / vol 2015–2025 |
|---|---|---|---|---|---|---|---|
| Market (benchmark) | 0.66 | 12.5% | 19.0% | −55% | 0.71 | 0.49 | 0.78 |
| **Averaged books (mom, gp, ag)** | **1.43** | 5.1% | 3.6% | −6% | 2.21 | 0.91 | 1.15 |
| Plain sum of Grinold alphas | 1.12 | 6.6% | 5.9% | −19% | 1.83 | 0.64 | 0.86 |
| Plain sum, cross-sectional mean σ | 1.20 | 7.0% | 5.9% | −14% | 1.69 | 0.96 | 0.98 |

**Single-signal books** (section 12, monthly returns)

| Long-short book | Net Sharpe | Beta | Alpha t-stat |
|---|---|---|---|
| Momentum (12-1) | 0.42 | −0.01 | 2.4 |
| Gross profitability | 0.48 | −0.02 | 2.8 |
| Asset growth | 0.44 | −0.01 | 2.4 |
| Short-term reversal | −0.02 | 0.08 | −0.7 |

* The signals are systematic. Unless they are added to the risk model as factors, their risk is
  underestimated 1.3–2.1×. Neutralizing them removes most of the alpha.
* The turnover penalty cuts turnover 3–6× and raises net Sharpe. Reversal only works before costs.
* Sector factors matter a lot. Extra covariance shrinkage did not help.
* The final books are almost uncorrelated with the market (correlation +0.04).
