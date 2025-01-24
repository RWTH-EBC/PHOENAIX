import copy
import numpy as np

devices_zero = {
    "bat": {"cap": 0.0, "eta_ch": 0.95, "eta_dch": 0.95, "k_loss": 0.0, "max_ch": 0.6, "max_dch": 0.6,
            "max_soc": 0.95, "min_soc": 0.05},
    "boiler": {"cap": 0.0, "eta_th": 0.97},
    "chp": {"cap": 0.0, "eta_el": 0.3, "eta_th": 0.62},
    "eh": {"cap": 0.0, "eta": 1.0},
    "fc": {"cap": 0.0, "eta_el": 0.39, "eta_th": 0.53}, "hp35": {"cap": 0.0, "dT_max": 15.0},
    "hp55": {"cap": 0.0, "dT_max": 15.0},
    "tes": {"cap": 0.0, "dT_max": 35, "eta_ch": 1, "eta_dch": 1, "k_loss": 0.02, "max_soc": 1.0,
            "min_soc": 0.0}
    }

devices_tes_and_bat = copy.deepcopy(devices_zero)
devices_tes_and_bat["tes"]["cap"] = 23
devices_tes_and_bat["bat"]["cap"] = 9

devices_boiler = copy.deepcopy(devices_tes_and_bat)
devices_boiler["boiler"]["cap"] = 11

devices_hp_35 = copy.deepcopy(devices_tes_and_bat)
devices_hp_35["hp35"]["cap"] = 8
devices_hp_35["eh"]["cap"] = 14

devices_hp_55 = copy.deepcopy(devices_tes_and_bat)
devices_hp_55["hp55"]["cap"] = 13
devices_hp_55["eh"]["cap"] = 3.3

nodes_basic = {
    "devs": devices_zero,
    "type": "SFH",
    "elec": [3]*8760,
    "heat": [4]*8760,
    "dhw": [2]*8760,
    "pv_power": [1]*8760,
    "T_air": [10]*8760
}

nodes_boiler = copy.deepcopy(nodes_basic)
nodes_boiler["devs"] = devices_boiler

nodes_hp_55 = copy.deepcopy(nodes_basic)
nodes_hp_55["devs"] = devices_hp_55
nodes_hp_55["pv_power"] = [10]*8760

forecast = {
    "power_demand": [3]*36,
    "heat_demand": [4]*36,
    "dhw_demand": [2]*36,
    "pv_power": [1]*36,
    "T_air": [10]*36
    }
forecast_no_pv = forecast.copy()
forecast_no_pv["pv_power"] = [0]*36

forecast_high_pv = forecast.copy()
forecast_high_pv["pv_power"] = [8]*36

building_params_SFH = {
    "type": "SFH",
    "rated_power": 30.484
    }

soc = {
    "tes": 1,
    "bat": 2
    }

flexibility_zero = {
    "energy_bid_avg_delayed_heat": 0,
    "energy_bid_avg_forced_bat": 0,
    "energy_bid_avg_forced_heat": 0,
    "energy_bid_avg_delayed_bat": 0
    }

flexibility_50 = {
    "energy_bid_avg_delayed_heat": 50,
    "energy_bid_avg_forced_bat": 50,
    "energy_bid_avg_forced_heat": 50,
    "energy_bid_avg_delayed_bat": 50
    }

flexibility_100 = {
    "energy_bid_avg_delayed_heat": 100,
    "energy_bid_avg_forced_bat": 100,
    "energy_bid_avg_forced_heat": 100,
    "energy_bid_avg_delayed_bat": 100
    }

trading_constraints_buying = {
    "min_P_trade_buy": np.zeros(36),
    "min_P_trade_sell": np.zeros(36),
    "P_prev_trades_buy": np.concatenate(([1, 2, 1.5], np.zeros(33))),
    "P_prev_trades_sell": np.concatenate(([0, 0, 0], np.zeros(33))),
    "max_P_trade_buy_sum": 100,
    "max_P_trade_sell_sum": 0,
    "max_P_buy_total_sum": 200,
    "max_P_sell_total_sum": 0,
    "max_P_trade_buy": np.concatenate(([5, 3, 3], np.zeros(33))),
    "max_P_trade_sell": np.zeros(36),
    "price_trade_buy": np.concatenate(([0.2, 0.3, 0.1], np.zeros(33))),
    "price_trade_sell": np.zeros(36)
}

trading_constraints_selling = {
    "min_P_trade_buy": np.zeros(36),
    "min_P_trade_sell": np.zeros(36),
    "P_prev_trades_buy": np.concatenate(([0, 0, 0], np.zeros(33))),
    "P_prev_trades_sell": np.concatenate(([1, 2, 1.5], np.zeros(33))),
    "max_P_trade_buy_sum": 0,
    "max_P_trade_sell_sum": 100,
    "max_P_buy_total_sum": 0,
    "max_P_sell_total_sum": 200,
    "max_P_trade_buy": np.zeros(36),
    "max_P_trade_sell": np.concatenate(([5, 3, 3], np.zeros(33))),
    "price_trade_buy": np.zeros(36),
    "price_trade_sell": np.concatenate(([0.2, 0.3, 0.1], np.zeros(33))),
}