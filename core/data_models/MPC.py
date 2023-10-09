from core.data_models import Device
import time
import threading
import random


class MPC(Device):
    def __init__(self, *args, **kwargs):

        # setup entity type (fix the entity type)
        self.entity_type = "MPC"



    def rolling_horizon_params(self):
        # Set rolling horizon options
        # TODO: options rh into json input file
        param_rh = {
            # Parameters for operational optimization
            "n_hours": 36,  # ----,      number of hours of prediction horizon for rolling horizon
            "n_hours_ov": 35,  # ----,      number of hours of overlap horizon for rolling horizon
            "n_opt_max": 8760,  # 8760  # -----,       maximum number of optimizations
            "month": 1,  # -----,     optimize this month 1-12 (1: Jan, 2: Feb, ...), set to 0 to optimize entire year
            # Parameters for rolling horizon with aggregated foresight
            "n_blocks": 2,
            # ----, number of blocks with different resolution: minimum 2 (control horizon and overlap horizon)
            # "resolution": [0.25, 1],  # h,    time resolution of each resolution block, insert list
            "resolution": [1, 1],  # h,    time resolution of each resolution block, insert list
            # [0.25, 1] resembles: control horizon with 15min, overlap horizon with 1h discretization
            "overlap_block_duration": [0, 0],
        }  # h, duration of overlap time blocks, insert 0 for default: half of overlap horizon

        # Months and starting hours of months
        param_rh["month_start"] = {}
        param_rh["month_start"][1] = 0
        param_rh["month_start"][2] = 744
        param_rh["month_start"][3] = 1416
        param_rh["month_start"][4] = 2160
        param_rh["month_start"][5] = 2880
        param_rh["month_start"][6] = 3624
        param_rh["month_start"][7] = 4344
        param_rh["month_start"][8] = 5088
        param_rh["month_start"][9] = 5832
        param_rh["month_start"][10] = 6552
        param_rh["month_start"][11] = 7296
        param_rh["month_start"][12] = 8016
        param_rh["month_start"][13] = 8760  # begin of next year

        # %% ROLLING HORIZON SET UP: Time steps, etc.

            # Example to explain set up:    n_hours: 48
            #                               n_hours_ov: 36
            #                           --> n_hours_ch: 12
            #                               n_blocks: 2
            #                               resolution: [1,6]

        # Calculate duration of each time block
        param_rh["org_block_duration"] = {}  # original block duration (for example: [12,36])
        param_rh["block_duration"] = {}  # block duration with another resolution (for example: [12/1,36/6]=[12,6])

        # First block (block 0): control horizon (detailed time series)
        param_rh["org_block_duration"][0] = param_rh["n_hours"] - param_rh["n_hours_ov"]
        param_rh["n_hours_ch"] = param_rh["org_block_duration"][0]
        param_rh["block_duration"][0] = int(param_rh["org_block_duration"][0] / param_rh["resolution"][0])

        # Remaining blocks: overlap horizon (aggregated time series)
        # Default duration of overlap block: total duration of overlap horizon equally split up to number of blocks (only if division yields integer)
        if sum(param_rh["overlap_block_duration"][i] for i in range(param_rh["n_blocks"])) == 0:
            # take default
            for b in range(1, param_rh["n_blocks"]):
                param_rh["org_block_duration"][b] = int(np.floor(param_rh["n_hours_ov"] / (param_rh["n_blocks"] - 1)))
                param_rh["block_duration"][b] = int(param_rh["org_block_duration"][b] / param_rh["resolution"][b])
        else:
            # take durations specified above
            for b in range(1, param_rh["n_blocks"]):
                param_rh["org_block_duration"][b] = int(param_rh["overlap_block_duration"][b])

        # Set up time steps

        # optimize any period of length n_opt_max*n_hours_ch or entire year starting at hour 0
        if param_rh["month"] == 0:  # optimize entire year

            # Calculate number of operational optimizations
            param_rh["n_opt_total"] = int(np.ceil(8760 / param_rh["n_hours_ch"]))
            # Number of optimizations: Take minimum out of maximum optimizations or total optimizations needed to cover entire year
            param_rh["n_opt"] = min(param_rh["n_opt_total"], param_rh["n_opt_max"])

            # Set up starting hour of each optimization
            param_rh["hour_start"] = {}  # starting hour of each optimization
            for i in range(param_rh["n_opt"]):
                # Starting hour of each optimization
                param_rh["hour_start"][i] = i * param_rh["n_hours_ch"]

        else:  # optimize only selected month (param["month"] specifies number of selected month)

            # Calculate total number of hours within chosen month
            hours_month = param_rh["month_start"][param_rh["month"] + 1] - param_rh["month_start"][param_rh["month"]]

            # Calculate number of optimizations
            # param["n_opt"] = int(np.ceil(hours_month / param["n_hours_ch"]))
            param_rh["n_opt"] = min(int(np.ceil(hours_month / param_rh["n_hours_ch"])), param_rh["n_opt_max"])

            # Set up starting hour of each optimization
            param_rh["hour_start"] = {}  # starting hour of each optimization
            for i in range(param_rh["n_opt"]):
                # Starting hour of each optimization
                param_rh["hour_start"][i] = param_rh["month_start"][param_rh["month"]] + i * param_rh["n_hours_ch"]

        param_rh["end_time_org"] = param_rh["n_opt"] * param_rh["n_hours_ch"]  # relevant for soc_end = soc_init

        # Set up optimization time steps (incl. aggregated foresight time steps)
        param_rh["time_steps"] = {}  # time steps for optimization incl. aggregation, for 1st optimization for example above:
        # [0,1,2,3,4,5,6,7,8,9,10,11, 12,13,14,15,16,17]
        param_rh["org_time_steps"] = {}  # original time steps for optimizations, for 1st optimization for example above:
        # [0,1,2,3,4,5,6,7,8,9,10,11, 12,18,24,30,36,42]
        param_rh["duration"] = {}  # indicates duration of each time step

        # Set up time steps for each optimization
        for i in range(param_rh["n_opt"]):

            param_rh["time_steps"][i] = []
            param_rh["duration"][i] = {}

            # for each block, set up time steps
            # only time steps where the original corresponding time steps are still within 8760 hours are set up
            count = param_rh["hour_start"][i]  # corresponding original time step
            step = param_rh["hour_start"][i]  # number of time step
            for b in range(param_rh["n_blocks"]):
                for t in range(param_rh["block_duration"][b]):
                    h_end = count + param_rh["resolution"][b]  # ending hour of original time step
                    if h_end < 8760:  # only if ending hour of original time step smaller than 8760
                        param_rh["time_steps"][i].append(step)  # append optimization time step
                        param_rh["duration"][i][step] = param_rh["resolution"][b]  # duration of optimization time step is resolution of respective block
                    else:  # if ending hour of original time step is >= 8760
                        rest = param_rh["resolution"][b] - (h_end - 8760)  # remaining original time steps still lying within the year
                        if rest > 0:  # are remaining time steps existing?
                            param_rh["time_steps"][i].append(step)  # append optimization time step
                            param_rh["duration"][i][step] = rest  # duration of optimization time step is number of remaining time steps
                    count = h_end  # set ending hour of one time step as starting hour of next one
                    step = step + 1  # next optimization time step

        # Set up original time steps (for each optimization time step, corresponding starting hour of original time step)
        for i in range(param_rh["n_opt"]):
            param_rh["org_time_steps"][i] = []
            param_rh["org_time_steps"][i].append(param_rh["time_steps"][i][0])  # first original time step
            count = 0

            # add original time steps for each optimization time step using starting hour and duration of previous time step
            for t in range(param_rh["time_steps"][i][0], param_rh["time_steps"][i][-1]):
                # if count > 0:
                param_rh["org_time_steps"][i].append(param_rh["org_time_steps"][i][-1] + param_rh["duration"][i][t])

        # adjust the following values
        param_rh["datapoints"] = int(8760 / options["discretization_input_data"])

    def mpc_params(self):

        param_mpc = {}
        param_mpc["eco"] = {}
        param_mpc["gp"] = {}

        # Always EUR per kWh (meter per anno)
        param_mpc["eco"]["sell_pv"] = 0.082  # €/kWh valid for pv systems with < 10 kWp
        param_mpc["eco"]["el_grid"] = 0.42
        param_mpc["eco"]["gas"] = 0.134  # Durchschnitt Januar 2023, Quelle Handelsblatt

        param_mpc["gp"]["mip_gap"] = 0.01  # https://www.gurobi.com/documentation/9.1/refman/mipgap2.html
        param_mpc["gp"]["time_limit"] = 100  # [s]  https://www.gurobi.com/documentation/9.1/refman/timelimit.html
        param_mpc["gp"]["numeric_focus"] = 3  # https://www.gurobi.com/documentation/9.1/refman/numericfocus.html


    def get_forecast_demand(self):

    def get_real_demand(self):

    def get_forecast_weather(self):

    def get_real_weather(self):

    def run_central_optimization(self, demands, devs, weather, param_mpc, param_rh, init_val, n_opt):

        # Define subsets
        heater = ("boi", "eh", "hp")
        storage = ("tes",)
        solar = ("pv",)
        device = heater + storage + solar

        # Extract parameters
        dt = param_rh["duration"][n_opt]
        # Create list of time steps per optimization horizon (dt --> hourly resolution)
        time_steps = param_rh["time_steps"][n_opt]
        # time_steps = range(params["time_steps"])  # ohne RH
        # Durations of time steps # for aggregated RH
        duration = param_rh["duration"][n_opt]

        model = gp.Model("Design computation")

        # Initialization: only if initial values have been generated in previous prediction horizon
        soc_init_rh = {}
        if bool(init_val) == True:
            # initial SOCs
            # Buildings
            for n in devs:
                soc_init_rh[n] = {}
                for dev in storage:
                    soc_init_rh[n][dev] = init_val["soc"][n][dev]

        if param_rh["month"] == 0:
            param_rh["month"] = param_rh["month"] + 1

        # Define variables
        # Costs and Revenues
        c_dem = {dev: model.addVar(vtype="C", name="c_dem_" + dev)
                 for dev in ("gas", "grid")}

        revenue = {"grid_pv": model.addVar(vtype="C", name="revenue_" + "grid_pv")
                   }

        # SOC, charging, discharging, power and heat
        soc = {}
        p_ch = {}
        p_dch = {}
        power = {}
        heat = {}
        for n in devs:
            soc[n] = {}
            p_ch[n] = {}
            p_dch[n] = {}
            for dev in storage:  # All storage devices
                soc[n][dev] = {}
                p_ch[n][dev] = {}
                p_dch[n][dev] = {}
                for t in time_steps:  # All time steps of all days
                    soc[n][dev][t] = model.addVar(vtype="C", lb=0, name="SOC_" + dev + "_" + str(t))
                    p_ch[n][dev][t] = model.addVar(vtype="C", lb=0, name="P_ch_" + dev + "_" + str(t))
                    p_dch[n][dev][t] = model.addVar(vtype="C", lb=0, name="P_dch_" + dev + "_" + str(t))

        for n in devs:
            power[n] = {}
            heat[n] = {}
            for dev in ["hp", "boi"]:
                power[n][dev] = {}
                heat[n][dev] = {}
                for t in time_steps:
                    power[n][dev][t] = model.addVar(vtype="C", lb=0, name="P_" + dev + "_" + str(t))
                    heat[n][dev][t] = model.addVar(vtype="C", lb=0, name="Q_" + dev + "_" + str(t))

        cop = {}
        for n in devs:
            cop[n] = {}
            for dev in ["hp"]:
                cop[n][dev] = {}
                for t in time_steps:
                    cop[n][dev][t] = model.addVar(vtype="C", lb=0, name="CoP_" + dev + "_" + str(t))

        for n in devs:
            for dev in ["eh"]:
                power[n][dev] = {}
                for t in time_steps:
                    power[n][dev][t] = model.addVar(vtype="C", lb=0, name="P_" + dev + "_" + str(t))

        for n in devs:
            for dev in ["pv"]:
                power[n][dev] = {}
                for t in time_steps:
                    power[n][dev][t] = model.addVar(vtype="C", lb=0, name="P_" + dev + "_" + str(t))

        # mapping storage sizes
        soc_nom = {}
        for n in devs:
            soc_nom[n] = {}
            for dev in storage:
                soc_nom[n][dev] = devs[n]["devs"][dev]["cap"]

        # Storage initial SOC's
        soc_init = {}
        for n in devs:
            soc_init[n] = {}
            soc_init[n]["tes"] = soc_nom[n]["tes"] * 0.5  # kWh   Initial SOC TES

        # storage devices: soc_end = soc_init
        # boolSOC = True
        # if boolSOC:
        #    if par_rh["end_time_org"] in par_rh["org_time_steps"][n_opt]:
        #        index_end = par_rh["org_time_steps"][n_opt].index(par_rh["end_time_org"])
        #        time_step_end = par_rh["time_steps"][n_opt][index_end]

        #        for n in nodes:
        #            for dev in storage:
        #                model.addConstr(soc[n][dev][time_step_end] == soc_init[n][dev],
        #                                name = "soc_end == soc_init for " + str(dev) + " in BES: " +str(n) + " for n_opt: " + str(n_opt))

        # Electricity imports, sold and self-used electricity
        p_imp = {}
        p_use = {}
        p_sell = {}
        y_imp = {}
        for n in devs:
            p_imp[n] = {}
            y_imp[n] = {}
            p_use[n] = {}
            p_sell[n] = {}
            for t in time_steps:
                p_imp[n][t] = model.addVar(vtype="C", lb=0, name="P_imp_" + str(t))
                y_imp[n][t] = model.addVar(vtype="B", lb=0.0, ub=1.0, name="y_imp_exp_" + str(t))
            for dev in ["pv"]:

                p_use[n][dev] = {}
                p_sell[n][dev] = {}
                for t in time_steps:
                    p_use[n][dev][t] = model.addVar(vtype="C", lb=0, name="P_use_" + dev + "_" + str(t))
                    p_sell[n][dev][t] = model.addVar(vtype="C", lb=0, name="P_sell_" + dev + "_" + str(t))

        # Gas imports to devices
        gas = {}
        for n in devs:
            gas[n] = {}
            for dev in ["boi"]:

                gas[n][dev] = {}
                for t in time_steps:
                    gas[n][dev][t] = model.addVar(vtype="C", lb=0, name="gas" + dev + "_" + str(t))

        # activation variable for trafo load
        yTrafo = model.addVars(time_steps, vtype="B", name="yTrafo_" + str(t))

        # %% BALANCING UNIT VARIABLES

        # Residual network demand
        residual = {}
        residual["demand"] = {}  # Residual network electricity demand
        residual["feed_pv"] = {}  # Residual feed in pv
        power["from_grid"] = {}
        power["to_grid"] = {}
        gas_dom = {}

        for t in time_steps:
            residual["demand"][t] = model.addVar(vtype="C", lb=0, name="residual_demand_t" + str(t))
            residual["feed_pv"][t] = model.addVar(vtype="C", lb=0, name="residual_feed_pv_t" + str(t))
            power["from_grid"][t] = model.addVar(vtype="C", lb=0, name="district_demand_t" + str(t))
            power["to_grid"][t] = model.addVar(vtype="C", lb=0, name="district_feed_t" + str(t))
            gas_dom[t] = model.addVar(vtype="C", lb=0, name="gas_demand_t" + str(t))

        # Electrical power to/from devices
        for device in ["el_from_grid", "el_to_grid", "gas_from_grid"]:
            power[device] = {}
            for t in time_steps:
                power[device][t] = model.addVar(vtype="C", lb=0, name="power_" + device + "_t" + str(t))

        # total energy amounts taken from grid
        from_grid_total_el = model.addVar(vtype="C", lb=0, name="from_grid_total_el")
        # total power to grid
        to_grid_total_el = model.addVar(vtype="C", lb=0, name="to_grid_total_el")
        # total gas amounts taken from grid
        from_grid_total_gas = model.addVar(vtype="C", lb=0, name="from_grid_total_gas")

        network_load = model.addVar(vtype="c", lb=-gp.GRB.INFINITY, name="peak_network_load")

        # Update
        model.update()

        # Objective
        # TODO:
        model.setObjective(c_dem["grid"] + c_dem["gas"] - revenue["grid_pv"]
                           + network_load * 0.01, gp.GRB.MINIMIZE)

        # Network load
        model.addConstrs(network_load >= power["from_grid"][t] for t in time_steps)

        for n in devs:
            for t in time_steps:
                model.addConstr(y_imp[n][t] * 1000 >= p_imp[n][t], name="Max_el_imp_" + str(t))
                model.addConstr((1 - y_imp[n][t]) * 1000 >= p_sell[n]["PV"][t] + p_sell[n]["CHP"][t],
                                name="Max_el_exp_" + str(t))

        ####### Define constraints

        ##### Economic constraints

        # Demand related costs (gas)
        model.addConstr(c_dem["gas"] == param_mpc["eco"]["gas"] * sum(dt[t] * gas_dom[t] for t in time_steps),
                        name="Demand_costs_gas")
        # Demand related costs (electricity)
        model.addConstr(
            c_dem["grid"] == param_mpc["eco"]["el_grid"] * sum(dt[t] * residual["demand"][t] for t in time_steps),
            name="Demand_costs_el_grid")
        # Revenues for selling electricity to the grid / neighborhood
        model.addConstr(
            revenue["grid_pv"] == param_mpc["eco"]["sell_pv"] * sum(dt[t] * residual["feed_pv"][t] for t in time_steps),
            name="Feed_in_rev_pv")


        ###### Technical constraints

        # Determine nominal heat at every timestep
        for n in devs:
            for t in time_steps:
                for dev in ["hp", "boiler", "eh"]:
                    # for dev in ["hp35", "hp55", "chp", "boiler", "eh"]:

                    if dev == "EH":
                        model.addConstr(power[n][dev][t] <= devs[n]["devs"][dev]["cap"])
                    else:
                        model.addConstr(heat[n][dev][t] <= devs[n]["devs"][dev]["cap"],
                                        name="Max_heat_operation_" + dev)

        ### Devices operation
        # Heat output between mod_lvl*Q_nom and Q_nom (P_nom for heat pumps)
        # Power and Energy directly result from Heat output
        for n in devs:
            for t in time_steps:
                # Heatpumps
                dev = "HP"
                model.addConstr(heat[n][dev][t] == power[n][dev][t] * cop[n][dev][t],
                                name="Power_equation_" + dev + "_" + str(t))
                model.addConstr(cop[n][dev][t] == 0.4 * (273.15 + 35) / (35 - T_air[t]),
                                name="CoP_equation_" + dev + "_" + str(t))

                # BOILER
                dev = "boiler"
                model.addConstr(heat[n]["boiler"][t] == devs[n]["devs"]["boiler"]["eta_th"] * gas[n]["boiler"][t],
                                name="Power_equation_" + dev + "_" + str(t))

        # Solar components
        for n in devs:
            for dev in solar:
                for t in time_steps:
                    model.addConstr(power[n][dev][t] == nodes[n]["pv_power"][t],
                                    name="Solar_electrical_" + dev + "_" + str(t))

        # power of the electric heater
        for n in devs:
            # eletric heater covers 50% of the dhw
            for t in time_steps:
                if devs[n]["devs"]["eh"]["cap"] == 0.0:
                    model.addConstr(power[n]["eh"][t] == 0, name="El_heater_act_" + str(t))
                else:
                    model.addConstr(power[n]["eh"][t] == 0.5 * demands[n]["dhw"][t],
                                    name="El_heater_act_" + str(t))

        # %% BUILDING STORAGES # %% DOMESTIC FLEXIBILITIES

        ### TES CONSTRAINTS CONSTRAINTS
        dev = "tes"
        for n in devs:
            eta_tes = devs[dev]["eta_tes"]
            eta_ch = devs[dev]["eta_ch"]
            eta_dch = devs[dev]["eta_dch"]

            for t in time_steps:
                # Initial SOC is the SOC at the beginning of the first time step, thus it equals the SOC at the end of the previous time step
                if t == param_rh["hour_start"][n_opt] and t > param_rh["month_start"][param_rh["month"]]:
                    soc_prev = soc_init_rh[n][dev]
                elif t == param_rh["month_start"][param_rh["month"]]:
                    soc_prev = soc_init[n][dev]
                else:
                    soc_prev = soc[n][dev][t - 1]

                # Maximal charging
                model.addConstr(p_ch[n][dev][t] == eta_ch * (heat[n]["hp"][t] + heat[n]["boi"][t]),
                                name="Heat_charging_" + str(t))
                # Maximal discharging
                if devs[n]["eh"]["cap"] == 0.0:
                    model.addConstr(p_dch[n][dev][t] == (1 / eta_dch) * (
                            demands[n]["heat"][t] + demands[n]["dhw"][t]),
                                    name="Heat_discharging_" + str(t))
                else:
                    model.addConstr(p_dch[n][dev][t] == (1 / eta_dch) * (
                            demands[n]["heat"][t] + 0.5 * demands[n]["dhw"][t]),
                                    name="Heat_discharging_" + str(t))

                # Minimal and maximal soc
                # model.addConstr(soc[n]["TES"][t] <= soc_nom[n]["TES"], name="max_cap_tes_" + str(t))
                # model.addConstr(soc[n]["TES"][t] >= nodes[n]["devs"]["TES"]["min_soc"] * soc_nom[n]["TES"],
                #                name="min_cap_" + str(t))

                # SOC coupled over all times steps (Energy amount balance, kWh)
                model.addConstr(soc[n][dev][t] == soc_prev * eta_tes + dt[t] * (p_ch[n][dev][t] - p_dch[n][dev][t]),
                                name="Storage_bal_" + dev + "_" + str(t))

            # TODO: soc at the end is the same like at the beginning
            # if t == last_time_step:
            #    model.addConstr(soc[device][t] == soc_init[device],
            #                    name="End_TES_Storage_" + str(t))


        # Electricity balance (house)
        for n in devs:
            for t in time_steps:
                model.addConstr(demands[n]["elec"][t]
                                + power[n]["hp"][t] + power[n]["eh"][t]
                                - p_use[n]["pv"][t]
                                == p_imp[n][t],
                                name="Electricity_balance_" + str(t))

        # Split CHP and PV generation into self-consumed and sold powers
        for n in devs:
            for dev in ("pv"):

                for t in time_steps:
                    model.addConstr(p_sell[n][dev][t] + p_use[n][dev][t] == power[n][dev][t],
                                    name="power=sell+use_" + dev + "_" + str(t))

        ### energy balance neighborhood

        # Residual loads
        for t in time_steps:
            # Residual network electricity demand (Power balance, MW)
            model.addConstr(residual["demand"][t] == sum(p_imp[n][t] for n in devs))
            model.addConstr(residual["feed_pv"][t] == sum(p_sell[n]["pv"][t] for n in devs))
            # Gas balance (power)
            model.addConstr(gas_dom[t] == sum(gas[n]["boi"][t] for n in devs),
                            name="Demand_gas_total")

        # Total gas amounts taken from grid (Energy amounts, MWh)
        model.addConstr(from_grid_total_gas == sum(dt[t] * power["gas_from_grid"][t] for t in time_steps))
        # Total electricity amounts taken from grid (Energy amounts, MWh)
        model.addConstr(from_grid_total_el == sum(dt[t] * power["from_grid"][t] for t in time_steps))
        # Total electricity feed-in (Energy amounts, MWh)
        model.addConstr(to_grid_total_el == sum(dt[t] * power["to_grid"][t] for t in time_steps))

        # Set solver parameters
        model.Params.TimeLimit = param_mpc["gp"]["time_limit"]
        model.Params.MIPGap = param_mpc["gp"]["mip_gap"]
        model.Params.MIPFocus = param_mpc["gp"]["numeric_focus"]

        # Execute calculation
        model.optimize()
        if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
            IISconstr = []
            model.computeIIS()
            f = open('errorfile_hp.txt', 'w')
            f.write('\nThe following constraint(s) cannot be satisfied:\n')
            for c in model.getConstrs():
                if c.IISConstr:
                    f.write('%s' % c.constrName)
                    f.write('\n')
                    IISconstr.append(c.constrName)
            f.close()

        # Retrieve results
        t = n_opt
        res_y = {}
        res_power = {}
        res_heat = {}
        res_soc = {}
        res_p_ch = {}
        res_p_dch = {}
        res_p_imp = {}
        res_gas = {}
        res_c_dem = {}
        res_soc_nom = {}
        res_p_use = {}
        res_p_sell = {}
        res_rev = {}
        for n in devs:
            res_y[n] = {}
            res_power[n] = {}
            res_heat[n] = {}
            res_soc[n] = {}
            res_p_ch[n] = {}
            res_p_dch[n] = {}
            res_p_imp[n] = {}
            res_gas[n] = {}
            res_c_dem[n] = {}
            res_soc_nom[n] = {}
            res_p_use[n] = {}
            res_p_sell[n] = {}
            res_rev[n] = {}

            # for dev in ["BAT", "EV", "house_load"]:
            res_y[n] = {(t): y_imp[n][t].X}
            for dev in ["hp", "boil"]:
                res_power[n][dev] = {(t): power[n][dev][t].X}
                res_heat[n][dev] = {(t): heat[n][dev][t].X}
            for dev in ["pv"]:
                res_power[n][dev] = {(t): power[n][dev][t].X}
            for dev in storage:
                res_soc[n][dev] = {(t): soc[n][dev][t].X}
            for dev in storage:
                res_p_ch[n][dev] = {(t): p_ch[n][dev][t].X}
                res_p_dch[n][dev] = {(t): p_dch[n][dev][t].X}
            for dev in ["boi"]:
                res_gas[n][dev] = {(t): gas[n][dev][t].X}

            res_c_dem[n]["c_gas"] = {
                (t): param_mpc["eco"]["gas"] * gas[n]["boi"][t].X }
            res_c_dem[n]["house_c_dem"] = {(t): p_imp[n][t].X * param_mpc["eco"]["el_grid"]}
            res_rev[n]["house_rev"] = {(t): p_sell[n]["pv"][t].X * param_mpc["eco"]["sell_pv"]}

            res_soc_nom[n] = {dev: soc_nom[n][dev] for dev in storage}
            for dev in ("pv"):
                res_p_use[n][dev] = {(t): p_use[n][dev][t].X}
                res_p_sell[n][dev] = {(t): p_sell[n][dev][t].X}
            res_p_imp[n] = {(t): p_imp[n][t].X}

        res_c_dem["ONT_c_dem"] = {(t): power["from_grid"][t].X * param_mpc["eco"]["el_grid"]}

        res_p_to_grid = {(t): power["to_grid"][t].X}
        res_p_from_grid = {(t): power["from_grid"][t].X}
        res_gas_from_grid = {(t): gas_dom[t].X}
        res_p_feed_pv = {(t): residual["feed_pv"][t].X}
        res_p_demand = {(t): residual["demand"][t].X}

        obj = model.ObjVal
        print("Obj: " + str(model.ObjVal))

        # Return results
        return (res_y, res_power, res_heat, res_soc, res_p_imp,
                res_p_ch, res_p_dch, res_p_use, res_p_sell, res_gas,
                res_c_dem, res_rev,
                res_p_to_grid, res_p_from_grid,
                res_gas_from_grid, res_p_feed_pv, res_p_demand)


    def run_fmu(self):




if __name__ == '__main__':
    MPC = MPC(entity_id="MPC:01")

