# Alpha 合约监控看板（阶段 A）

监控**已上 Binance Alpha、已上 USDⓈ-M 永续、未上 Binance 现货**的代币，粗筛"是否有人建仓或操盘"。
定位是 screening，口径大致正确即可。

```
Universe = Alpha ∩ Binance 永续(TRADING) − Binance 现货(TRADING)
```

架构：GitHub Actions 定时抓数 → `fetcher` 计算指标 → 写 `data/history.db` + `site/data.json` → 部署 `site/` 到 GitHub Pages。网页只读 `data.json`，不调用任何外部 API。免费数据源，无需 API key。

## 本地运行

```bash
pip install -r requirements.txt
python -m fetcher.main --out site/data.json     # 首次约 2–3 分钟（CoinGecko 限速，之后有 24h 缓存）
python -m http.server -d site                   # 打开 http://localhost:8000
```

可选参数：`--no-cg` 跳过 CoinGecko；`--no-store` 不写 SQLite。

任一必需数据源（合约/现货/Alpha 列表）失败 → 进程非零退出，**不覆盖**上一版 `data.json`；单币的 OI / DEX / CoinGecko 失败 → 对应字段 `null`，页面显示 "—"。

## 连通性测试（Step 0）

`connectivity-test.yml`（仅手动触发）在 GitHub runner 上逐个请求七个接口并打印状态码。

| 接口 | 本机（Danny，2026-10-06） | GitHub Actions runner |
|---|---|---|
| fapi.binance.com `/ping` `/exchangeInfo` | 200 | **451（被拒）** |
| api.binance.com `/exchangeInfo` | 200 | **451（被拒）** |
| data-api.binance.vision `/exchangeInfo` | 200 | 200 |
| Alpha `token/list` | 200 | 200 |
| DexScreener | 200 | 200 |
| CoinGecko `/ping` | 200 | 200 |

> 结论（2026-10-06 实测）：GitHub 托管 runner 访问 Binance 合约/现货 API 返回 451，**必须使用 self-hosted runner**（Alpha、DexScreener、CoinGecko 可用）。

### Self-hosted runner（Binance 被拒时）

1. 仓库 Settings → Actions → Runners → New self-hosted runner，选 macOS，按页面给出的命令在本机下载并 `./config.sh --url ... --token ...`。
2. `./run.sh` 前台运行，或 `sudo ./svc.sh install && sudo ./svc.sh start` 作为常驻服务。
3. 将 `update.yml` 与 `connectivity-test.yml` 中的 `runs-on: ubuntu-latest` 改为 `runs-on: self-hosted`，并确保本机有 Python 3.11（`actions/setup-python` 在自托管机上需要预装或改用本机 python）。
4. 本机关机时不会更新，可以接受。

## 部署到 GitHub Pages

1. 仓库必须是 **public**（免费版 Pages 需要）；代码和数据都会公开。
2. Settings → Pages → Source 选 **GitHub Actions**。
3. Actions 页手动触发一次 `update`；之后每 6 小时（`17 */6 * * *` UTC）自动运行。

## 修改阈值

编辑 `config/thresholds.yaml`（`warn` / `alert` / `direction` / `fmt`）。下一次运行后页面的着色与"方法论"区块同步变化，无需改代码。

## 使用 overrides

匹配失败或歧义的币会出现在页面底部"未匹配"列表和 `data.json.unmatched`。在 `config/overrides.yaml` 以合约 symbol 为 key 人工指定：

```yaml
XXXUSDT: { chain: bsc, address: "0xabc...", note: "Alpha 有两个同名币，取此地址" }  # 指定 Alpha 合约地址
YYYUSDT: { exclude: true }                                                           # 剔除
ZZZUSDT: { circ_source: cg }                                                         # 流通量改用 CoinGecko
WWWUSDT: { circ_source: manual, circ_supply: 123000000 }                             # 手填（单币口径）
```

匹配规则要点：
- 只取 USDT/USDC 永续；同一 base 两者 OI 与成交额相加，symbol 记主合约（USDT）。
- 合约 baseAsset 的 `1000` / `10000` / `1000000` / `1M` 前缀会被剥离并换算价格。
- 现货只要 `TRADING` 的 baseAsset 命中（不论计价币种）即排除。
- Alpha 状态：`fullyDelisted: true` 的币过滤；`offline: true` 但未完全摘牌的保留并标 💤（接口为非官方，字段含义由数据推断：`offline` + `offsell` = 停止 Alpha 交易，但 Binance 仍展示）。同名多币时优先选在线的。
- Alpha 同名多币：用合约价格校验（偏差 > 50% 视为同名不同币），多个候选时流动性最大者需 ≥ 次大者 5 倍才自动选用（标 🔀），否则进未匹配。

## 目录

```
fetcher/main.py          编排：universe → collect → metrics → store → export
fetcher/universe.py      匹配、归一化、排除、overrides
fetcher/metrics/stage_a.py   阶段 A 指标（以后加 stage_b.py / stage_c.py / scoring.py，实现同样的 compute(tok, cfg) 接口并加入 main.STAGES）
fetcher/sources/         各数据源适配
fetcher/store.py         SQLite（raw_json 保留原始字段，便于回补指标）
fetcher/export.py        data.json
config/                  thresholds.yaml, overrides.yaml
samples/alpha_list.json  Alpha 接口原始响应样本（非官方接口，字段可能变）
site/                    index.html + data.json
```

## 口径说明

- 价格统一用合约 mark price；OI 为名义价值（USD）。
- "现货量" 阶段 A 取 **DEX 24h 成交额**；Alpha 成交量含刷分水分且可能与 DEX 重叠，只单独展示。
- 流通量以 Alpha 为准；与 CoinGecko 差异 > 20% 打 `circ_mismatch`。
- 分母为 0 / null 的指标为 `na`，不计入警惕/偏热。

仅为数据筛选，不构成投资建议。
