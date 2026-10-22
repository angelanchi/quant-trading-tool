# -*- coding: utf-8 -*-
"""
CQF Module 4 — Supervised learning for direction, done honestly.

Pitfalls this module guards against:
  1. Look-ahead: features at t use data up to t only; label is the FUTURE return.
  2. Leakage across folds: TimeSeriesSplit with a gap = label horizon
     (overlapping labels would otherwise leak into the test fold).
  3. Fooling yourself: every score is shown next to a naive baseline
     (always predict the majority class of the TRAINING fold).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import binomtest


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def make_features(close: pd.Series, horizon: int = 5) -> pd.DataFrame:
    """Feature matrix + binary label (1 = price higher after `horizon` days)."""
    c = close.astype(float)
    r = np.log(c).diff()
    f = pd.DataFrame(index=c.index)
    f["ret_1"] = r
    f["ret_5"] = np.log(c / c.shift(5))
    f["ret_20"] = np.log(c / c.shift(20))
    f["mom_12_1"] = np.log(c.shift(21) / c.shift(252))
    f["vol_20"] = r.rolling(20).std() * np.sqrt(252)
    f["vol_ratio"] = r.rolling(5).std() / r.rolling(60).std()
    f["rsi_14"] = rsi(c, 14)
    f["dist_ma50"] = c / c.rolling(50).mean() - 1
    f["dist_ma200"] = c / c.rolling(200).mean() - 1
    fwd = np.log(c.shift(-horizon) / c)
    f["fwd_ret"] = fwd
    f["label"] = (fwd > 0).astype(float)
    f.loc[fwd.isna(), "label"] = np.nan
    return f


FEATURES = ["ret_1", "ret_5", "ret_20", "mom_12_1", "vol_20", "vol_ratio",
            "rsi_14", "dist_ma50", "dist_ma200"]


@dataclass
class WalkForwardReport:
    model: str
    horizon: int
    folds: pd.DataFrame
    predictions: pd.DataFrame = field(repr=False)
    importance: pd.Series = field(repr=False)

    @property
    def accuracy(self) -> float:
        p = self.predictions
        return float((p["pred"] == p["label"]).mean())

    @property
    def baseline_accuracy(self) -> float:
        """Naive baseline: majority class of each TRAINING fold (what you could know)."""
        p = self.predictions
        return float((p["baseline"] == p["label"]).mean())

    @property
    def hindsight_baseline(self) -> float:
        """Best constant guess chosen WITH hindsight on the test data (a strict bar)."""
        up = float(self.predictions["label"].mean())
        return max(up, 1 - up)

    @property
    def edge(self) -> float:
        """Accuracy above the STRICTER of the two baselines."""
        return self.accuracy - max(self.baseline_accuracy, self.hindsight_baseline)

    def significance(self) -> float:
        """
        One-sided binomial p-value vs the strict baseline, using only every
        `horizon`-th prediction so that labels do not overlap (independence).
        """
        p = self.predictions.iloc[:: max(self.horizon, 1)]
        k = int((p["pred"] == p["label"]).sum())
        n = len(p)
        base = max(self.baseline_accuracy, self.hindsight_baseline)
        base = min(max(base, 1e-6), 1 - 1e-6)
        return float(binomtest(k, n, base, alternative="greater").pvalue)

    def verdict(self) -> str:
        if self.edge <= 0.0 or self.significance() > 0.05:
            return "無可靠預測力：模型沒有穩定打贏基準"
        return "有統計上的優勢：仍需扣成本並做樣本外追蹤"


def walk_forward_classify(close: pd.Series, horizon: int = 5, model: str = "logistic",
                          n_splits: int = 5, seed: int = 0) -> WalkForwardReport:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    data = make_features(close, horizon).dropna(subset=FEATURES + ["label"])
    if len(data) < 300:
        raise ValueError("need roughly 300+ usable rows (about 2 years incl. 200-day warm-up)")
    X, y = data[FEATURES].values, data["label"].values.astype(int)

    def build():
        if model == "random_forest":
            return RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=20,
                                          random_state=seed, n_jobs=-1)
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=1000))

    tss = TimeSeriesSplit(n_splits=n_splits, gap=horizon)
    rows, preds, imps = [], [], []
    for i, (tr, te) in enumerate(tss.split(X)):
        clf = build().fit(X[tr], y[tr])
        p = clf.predict(X[te])
        prob = clf.predict_proba(X[te])[:, 1]
        majority = int(y[tr].mean() >= 0.5)
        preds.append(pd.DataFrame({"pred": p, "prob_up": prob, "baseline": majority,
                                   "label": y[te], "fwd_ret": data["fwd_ret"].values[te]},
                                  index=data.index[te]))
        rows.append({"fold": i + 1, "train_end": data.index[tr[-1]], "test_start": data.index[te[0]],
                     "test_end": data.index[te[-1]], "n_test": len(te),
                     "accuracy": float((p == y[te]).mean()),
                     "baseline": float((majority == y[te]).mean())})
        if model == "random_forest":
            imps.append(clf.feature_importances_)
        else:
            imps.append(np.abs(clf[-1].coef_[0]))
    imp = pd.Series(np.mean(imps, axis=0), index=FEATURES).sort_values(ascending=False)
    return WalkForwardReport(model=model, horizon=horizon, folds=pd.DataFrame(rows),
                             predictions=pd.concat(preds), importance=imp)


def strategy_curve(close: pd.Series, report: WalkForwardReport) -> pd.DataFrame:
    """
    Daily long/flat curve: hold next day when the model says 'up'.
    Compared with buy-and-hold over the SAME out-of-sample dates (costs excluded).
    """
    r = np.log(close.astype(float)).diff().shift(-1)  # next-day return
    p = report.predictions
    df = pd.DataFrame({"signal": p["pred"], "next_ret": r.reindex(p.index)}).dropna()
    df["strategy"] = np.exp((df["signal"] * df["next_ret"]).cumsum())
    df["buy_hold"] = np.exp(df["next_ret"].cumsum())
    return df
