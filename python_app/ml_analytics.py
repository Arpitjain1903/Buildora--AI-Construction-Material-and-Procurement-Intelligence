"""
SECTION 6: Supporting ML Components
Implements:
6.1 Price Trend Forecasting with Seasonality (Monsoon, Budget Cycles), 95% Confidence Intervals & Minimum-Data Guard
6.2 Supplier Reliability Scoring (Multi-factor weighted rule engine + Tiering)
6.3 Anomaly Detection (Correction 3.2: Modified Z-score M = 0.6745*(x - median)/MAD with threshold 3.5 & n >= 5,
    and small-sample % above median fallback)
"""

import math
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from scipy import stats

from python_app.constants_loader import CONSTANTS

# 6.1 Price Trend Forecasting
class PriceTrendForecaster:
    """
    Predicts 30/60/90 day price trends for materials given historical price series.
    Includes seasonality (Monsoon Jun-Sep, Union/State Budget Feb-Mar, Pre-monsoon Peak Apr-May),
    confidence intervals (95% standard error), and a minimum-data guard (refuses statistical forecast if n < 6).
    """
    MIN_OBSERVATIONS = 6

    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=40, random_state=42)
        self.is_trained = False
        self.training_sample_count = 0
        self.residual_std = 12.0 # default baseline error in INR

    def train_on_history(self, history_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Trains model on historical records.
        Refuses statistical training if history_data has fewer than MIN_OBSERVATIONS.
        """
        if not history_data or len(history_data) < self.MIN_OBSERVATIONS:
            self.is_trained = False
            return {
                "trained": False,
                "reason": f"Insufficient historical records. Minimum required: {self.MIN_OBSERVATIONS}, received: {len(history_data) if history_data else 0}",
                "records_count": len(history_data) if history_data else 0
            }

        X = []
        y = []
        for r in history_data:
            m = int(r.get("month", 6))
            is_monsoon = 1 if (6 <= m <= 9 or r.get("monsoon_flag", False)) else 0
            is_budget_cycle = 1 if (2 <= m <= 3 or r.get("budget_cycle_flag", False)) else 0
            X.append([
                float(r.get("past_price", 400.0)),
                m,
                int(r.get("region_code", 1)),
                float(r.get("fuel_index", 100.0)),
                is_monsoon,
                is_budget_cycle
            ])
            y.append(float(r.get("target_future_price", 420.0)))

        X_arr = np.array(X)
        y_arr = np.array(y)
        self.model.fit(X_arr, y_arr)
        preds = self.model.predict(X_arr)
        residuals = y_arr - preds
        self.residual_std = max(5.0, float(np.std(residuals)))
        self.is_trained = True
        self.training_sample_count = len(history_data)

        return {
            "trained": True,
            "records_count": self.training_sample_count,
            "residual_std": round(self.residual_std, 2)
        }

    def forecast_price_trend(
        self,
        current_price: float,
        month: int = 7,
        region_code: int = 1,
        fuel_index: float = 105.0,
        monsoon_flag: Optional[bool] = None,
        budget_cycle_flag: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Forecasts 30, 60, 90 day future prices with 95% confidence intervals and seasonal adjustments.
        """
        curr = max(1.0, float(current_price))
        is_monsoon = monsoon_flag if monsoon_flag is not None else (6 <= month <= 9)
        is_budget = budget_cycle_flag if budget_cycle_flag is not None else (2 <= month <= 3)

        # Seasonal multiplier calculations
        # Monsoon causes transport slow-down and localized delivery premiums
        monsoon_mult = 1.035 if is_monsoon else 1.0
        # Post-budget infrastructure spending surge
        budget_mult = 1.025 if is_budget else 1.0
        combined_seasonality = monsoon_mult * budget_mult

        if not self.is_trained:
            # Baseline deterministic heuristic forecast when insufficient training data
            f30 = round(curr * combined_seasonality * 1.01, 2)
            f60 = round(curr * combined_seasonality * 1.025, 2)
            f90 = round(curr * combined_seasonality * 1.04, 2)
            std_err = curr * 0.03
            data_status = "uncalibrated_heuristic_baseline (insufficient training history)"
        else:
            X_sample = np.array([[curr, month, region_code, fuel_index, 1 if is_monsoon else 0, 1 if is_budget else 0]])
            pred_base = float(self.model.predict(X_sample)[0])
            f30 = round(pred_base * combined_seasonality, 2)
            f60 = round(pred_base * combined_seasonality * 1.015, 2)
            f90 = round(pred_base * combined_seasonality * 1.03, 2)
            std_err = self.residual_std
            data_status = f"trained_on_{self.training_sample_count}_records"

        # 95% Confidence Intervals (Z = 1.96)
        ci_30 = [round(max(0.0, f30 - 1.96 * std_err), 2), round(f30 + 1.96 * std_err, 2)]
        ci_60 = [round(max(0.0, f60 - 1.96 * std_err * 1.2), 2), round(f60 + 1.96 * std_err * 1.2, 2)]
        ci_90 = [round(max(0.0, f90 - 1.96 * std_err * 1.4), 2), round(f90 + 1.96 * std_err * 1.4, 2)]

        change_pct = round(((f90 - curr) / curr) * 100.0, 1)
        trend_direction = "Bullish (Price Increase)" if change_pct > 2.0 else ("Bearish (Price Decrease)" if change_pct < -2.0 else "Stable")

        return {
            "current_price": curr,
            "forecast_30_days": f30,
            "confidence_interval_30_days_95": ci_30,
            "forecast_60_days": f60,
            "confidence_interval_60_days_95": ci_60,
            "forecast_90_days": f90,
            "confidence_interval_90_days_95": ci_90,
            "expected_change_pct": change_pct,
            "trend_direction": trend_direction,
            "model_status": data_status,
            "seasonality": {
                "monsoon_active": is_monsoon,
                "budget_cycle_active": is_budget,
                "seasonal_factor": round(combined_seasonality, 3)
            }
        }


# 6.2 Supplier Reliability Scoring
def calculate_supplier_reliability_score(
    on_time_delivery_pct: float = 92.0,
    defect_rate_pct: float = 2.0,
    price_stability_pct: float = 95.0,
    response_time_score: float = 90.0,
    w1: float = 0.35,
    w2: float = 0.30,
    w3: float = 0.20,
    w4: float = 0.15
) -> Dict[str, Any]:
    """
    Multi-Factor Supplier Reliability Scoring:
    Score = w1*(on-time %) + w2*(100 - defect_rate * 10) + w3*(price stability) + w4*(response time)
    """
    quality_score = max(0.0, 100.0 - (defect_rate_pct * 10.0))
    raw_score = (
        (w1 * on_time_delivery_pct) +
        (w2 * quality_score) +
        (w3 * price_stability_pct) +
        (w4 * response_time_score)
    )

    score_final = round(min(100.0, max(0.0, raw_score)), 1)

    if score_final >= 85.0:
        tier = "Tier A (Preferred Supplier)"
    elif score_final >= 70.0:
        tier = "Tier B (Approved Supplier)"
    else:
        tier = "Tier C (High Risk / Monitor)"

    return {
        "reliability_score": score_final,
        "tier": tier,
        "metrics": {
            "on_time_delivery_pct": on_time_delivery_pct,
            "defect_rate_pct": defect_rate_pct,
            "price_stability_pct": price_stability_pct,
            "response_time_score": response_time_score
        }
    }


# 6.3 Anomaly Detection (Correction 3.2: Modified Z-Score & Small Sample Fallback)
def detect_overinvoicing_anomalies(
    quotes_or_invoices: List[Dict[str, Any]],
    z_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Correction 3.2:
    Boris Iglewicz and David Hoaglin (1993) Modified Z-Score:
    M_i = 0.6745 * (x_i - median) / MAD
    Flag if |M_i| > 3.5. Requires n >= 5.

    If n < 5: Fall back to '% above median for same material/region'
    with configurable threshold (default 25.0% above median).
    """
    anom_cfg = CONSTANTS.get("anomaly_detection", {})
    thresh = z_threshold if z_threshold is not None else anom_cfg.get("modified_z_threshold", 3.5)
    min_obs = anom_cfg.get("min_observations_for_zscore", 5)
    small_sample_pct = anom_cfg.get("small_sample_median_pct_threshold", 25.0)
    mod_z_mult = anom_cfg.get("modified_z_multiplier", 0.6745)

    if not quotes_or_invoices:
        return []

    if len(quotes_or_invoices) == 1:
        item = dict(quotes_or_invoices[0])
        item["is_anomaly"] = False
        item["method_used"] = "single_item_no_comparison"
        item["regional_median_unit_cost"] = float(item.get("delivered_unit_cost", item.get("unitPrice", 0.0)))
        return [item]

    unit_costs = np.array([
        float(x.get("delivered_unit_cost", x.get("effective_unit_cost", x.get("unitPrice", 0.0))))
        for x in quotes_or_invoices
    ], dtype=float)

    median_val = float(np.median(unit_costs))
    n = len(unit_costs)

    results = []

    if n >= min_obs:
        # Modified Z-Score with MAD
        mad = float(np.median(np.abs(unit_costs - median_val)))
        for item, val in zip(quotes_or_invoices, unit_costs):
            res_item = dict(item)
            res_item["regional_median_unit_cost"] = round(median_val, 2)
            res_item["sample_size"] = n
            res_item["method_used"] = "modified_z_score (Iglewicz & Hoaglin 1993)"

            if mad > 1e-6:
                modified_z = float(mod_z_mult * (val - median_val) / mad)
                res_item["mad_zero_fallback"] = False
            else:
                # If MAD is 0 (more than half items have identical price), compute mean absolute deviation (MeanAD)
                mean_ad = float(np.mean(np.abs(unit_costs - median_val)))
                if mean_ad > 1e-6:
                    modified_z = float(mod_z_mult * (val - median_val) / mean_ad)
                    res_item["mad_zero_fallback"] = True
                    res_item["mad_zero_reason"] = "MAD was 0 due to >50% identical prices; fell back to Mean Absolute Deviation (MeanAD) denominator."
                else:
                    # All items are identical
                    modified_z = 0.0
                    res_item["mad_zero_fallback"] = True
                    res_item["mad_zero_reason"] = "All items have identical prices; zero deviation detected."

            res_item["modified_z_score"] = round(modified_z, 2)
            res_item["z_score"] = round(modified_z, 2) # backwards compatibility
            is_anom = abs(modified_z) > thresh
            res_item["is_anomaly"] = is_anom

            if is_anom:
                res_item["anomaly_reason"] = (
                    f"Unit cost deviates with Modified Z-score M={round(modified_z, 2)} "
                    f"(exceeds critical threshold |M| > {thresh}) against median {round(median_val, 2)}."
                )
            results.append(res_item)
    else:
        # Small sample fallback (n < 5): Percentage above median
        for item, val in zip(quotes_or_invoices, unit_costs):
            res_item = dict(item)
            res_item["regional_median_unit_cost"] = round(median_val, 2)
            res_item["sample_size"] = n
            res_item["method_used"] = f"small_sample_percentage_fallback (n={n} < {min_obs})"

            pct_above_median = float(((val - median_val) / median_val) * 100.0) if median_val > 0 else 0.0
            res_item["pct_above_median"] = round(pct_above_median, 1)
            is_anom = pct_above_median > small_sample_pct
            res_item["is_anomaly"] = is_anom
            res_item["z_score"] = round(pct_above_median / 10.0, 2) # scaled surrogate for backward-compat

            if is_anom:
                res_item["anomaly_reason"] = (
                    f"Unit cost is {round(pct_above_median, 1)}% above median ({round(median_val, 2)}), "
                    f"exceeding small-sample threshold (+{small_sample_pct}%)."
                )
            results.append(res_item)

    return results
