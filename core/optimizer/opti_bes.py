#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optimization model for energy center

@author: Joel Schölzel

"""

from __future__ import division

import gurobipy as gp
import datetime

def compute(demand, energyCenter_params, params, weather, par_rh, init_val, n_opt):

    # Define subsets
    heater = ("eh", "hp", "boi")
    storage = ("tes", )

    # Extract parameters
    dt = par_rh["dt"]
    # Create list of time steps per optimization horizon (dt --> hourly resolution)
    time_steps = par_rh["time_steps"][n_opt]

    model = gp.Model("Operation computation")

    # Initialization: only if initial values have been generated in previous prediction horizon
    #soc_init_rh = {}
    temp_tes_init_rh = {}
    if bool(init_val) == True:
        # initial SOCs
        for dev in storage:
            #soc_init_rh[dev] = init_val["soc"][dev]
            temp_tes_init_rh[dev] = init_val["temp_tes"][dev]

    if par_rh["month"] == 0:
        par_rh["month"] = par_rh["month"] + 1

    # Define variables
    # Costs and Revenues
    c_dem = {dev: model.addVar(vtype="C", name="c_dem_" + dev) for dev in ("boiler", "chp", "grid")}

    # SOC, charging, discharging, power and heat
    #soc = {}
    p_ch = {}
    p_dch = {}
    soc = {}
    power = {}
    heat = {}
    for dev in storage:  # All storage devices
        soc[dev] = {}
        p_ch[dev] = {}
        p_dch[dev] = {}
        for t in time_steps:  # All time steps of all days
            soc[dev][t] = model.addVar(vtype="C", name="SOC_" + dev + "_" + str(t))
            p_ch[dev][t] = model.addVar(vtype="C", name="P_ch_" + dev + "_" + str(t))
            p_dch[dev][t] = model.addVar(vtype="C", name="P_dch_" + dev + "_" + str(t))

    for dev in ["hp"]:
        power[dev] = {}
        heat[dev] = {}
        for t in time_steps:
            power[dev][t] = model.addVar(vtype="C", lb=0, name="P_" + dev + "_" + str(t))
            heat[dev][t] = model.addVar(vtype="C", lb=0, name="Q_" + dev + "_" + str(t))

    for dev in ["boi"]:
        heat[dev] = {}
        for t in time_steps:
            heat[dev][t] = model.addVar(vtype="C", lb=0, name="Q_" + dev + "_" + str(t))

    for dev in ["eh"]:
        power[dev] = {}
        for t in time_steps:
            power[dev][t] = model.addVar(vtype="C", lb=0, name="P_" + dev + "_" + str(t))

    # maping storage sizes
    soc_nom = {}
    for dev in storage:
        soc_nom[dev] = energyCenter_params[dev]["cap"]

    # Storage initial SOC's
    soc_init = {}
    soc_init["tes"] = soc_nom["tes"] * 0.5  # kWh   Initial SOC TES

    # Electricity imports, sold and self-used electricity
    p_imp = {}
    for t in time_steps:
        p_imp[t] = model.addVar(vtype="C", name="P_imp_" + str(t))

    # Update
    model.update()

    # Objective
    # TODO:
    model.setObjective(c_dem["grid"], gp.GRB.MINIMIZE)

    ####### Define constraints

    ##### Economic constraints

    # Demand related costs (electricity)    # eco["b"]["el"] * eco["crf"]
    dev = "grid"
    model.addConstr(c_dem[dev] == sum(p_imp[t] * params["eco"]["pr", "el"] for t in time_steps),
                    name="Demand_costs_" + dev)

    ###### Technical constraints

    # TODO: contraint einfügen: Wärmeleistung aus Auslegungspunkt, dann mit COP im AUslegungspunkts die el.Leisutng ausrechnen
    # TODO: Diese el Leistung ist dann für Betriebspunkte, ist das die max. el Leistung

    # Determine nominal heat at every timestep
    for t in time_steps:
        dev == "eh"
        model.addConstr(power[dev][t] <= energyCenter_params[dev]["cap"], name="Max_heat_operation_eh")

    ### Devices operation
    # Power and Energy directly result from Heat output
    for t in time_steps:
        # Heatpumps
        dev = "hp"
        model.addConstr(heat[dev][t] == power[dev][t] * COP["hp"][t], name="Power_equation_" + dev + "_" + str(t))

        model.addConstr(power[dev][t] <= y[dev][t] * energyCenter_params[dev]["cap"], name="Max_heat_operation_" + dev)
        model.addConstr(power[dev][t] >= y[dev][t] * 0, name="Min_heat_operation_" + dev)

        model.addConstr(COP["hp"][t] == 0.5 * (273.15 + T_VL[t]) / (T_VL[t] - weather["T_air"][t]), name="Power_equation_" + dev + "_" + str(t))




    # %% THERMICAL STORAGES  %%  FLEXIBILITIES

    ## Nominal storage content (SOC)
    # for dev in storage:
    #    # Inits
    #    model.addConstr(soc_init[dev] <= soc_nom[dev], name="SOC_nom_inits_"+dev)

    # Minimal and maximal charging, discharging and soc
    dev = "tes"
    eta_tes = energyCenter_params[dev]["eta_tes"]
    eta_ch = energyCenter_params[dev]["eta_ch"]
    eta_dch = energyCenter_params[dev]["eta_dch"]
    for t in time_steps:
        # Initial SOC is the SOC at the beginning of the first time step, thus it equals the SOC at the end of the previous time step
        if t == par_rh["hour_start"][n_opt] and t > par_rh["month_start"][par_rh["month"]]:
            soc_prev = soc_init_rh[dev]
        elif t == par_rh["month_start"][par_rh["month"]]:
            soc_prev = soc_init[dev]
        else:
            soc_prev = soc[dev][t - 1]

        # Maximal charging
        model.addConstr(p_ch[dev][t] == eta_ch * heat["hp"][t], name="Heat_charging_" + str(t))
        # Maximal discharging
        model.addConstr(p_dch[dev][t] == (1 / eta_dch) * (demand["heat"][t] ), name="Heat_discharging_" + str(t))

        # Minimal and maximal soc
        model.addConstr(soc["tes"][t] <= soc_nom["tes"], name="max_cap_tes_" + str(t))
        model.addConstr(soc["tes"][t] >= energyCenter_params["tes"]["min_soc"] * soc_nom["tes"], name="min_cap_" + str(t))

        # SOC coupled over all times steps (Energy amount balance, kWh)
        model.addConstr(soc[dev][t] == soc[dev][t - 1] * eta_tes + dt * (p_ch[dev][t] - p_dch[dev][t]),
                        name="Storage_bal_" + dev + "_" + str(t))

        model.addConstr((temp["tes"][t] - temp_tes_prev) * energyCenter_params["tes"]["vol"] \
                                        * energyCenter_params["tes"]["roh"] \
                                        * energyCenter_params["tes"]["c_p"] == dt * (p_ch[dev][t] - p_dch[dev][t]),
                        name="Storage_bal_" + dev + "_" + str(t))

        # TODO: soc at the end is the same like at the beginning
        # if t == last_time_step:
        #    model.addConstr(soc[device][t] == soc_init[device],
        #                    name="End_TES_Storage_" + str(t))

    # Electricity balance (house)
    for t in time_steps:
        model.addConstr(power["hp"][t] + power["eh"][t]  == p_imp[t], name="Electricity_balance_" + str(t))

    # Set solver parameters
    model.Params.TimeLimit = params["gp"]["time_limit"]
    model.Params.MIPGap = params["gp"]["mip_gap"]
    model.Params.MIPFocus = params["gp"]["numeric_focus"]

    # Execute calculation
    model.optimize()

    # Write errorfile if optimization problem is infeasible or unbounded
    if model.status == gp.GRB.Status.INFEASIBLE or model.status == gp.GRB.Status.INF_OR_UNBD:
        model.computeIIS()
        f = open('errorfile_energy_central.txt', 'w')
        f.write('\nThe following constraint(s) cannot be satisfied:\n')
        for c in model.getConstrs():
            if c.IISConstr:
                f.write('%s' % c.constrName)
                f.write('\n')
        f.close()

    # Retrieve results
    res_power = {}
    res_heat = {}
    res_soc = {}
    for dev in ["hp", "eh"]:
        res_power[dev] = {(t): power[dev][t].X for t in time_steps}
    for dev in ["hp", "boi"]:
        res_heat[dev] = {(t): heat[dev][t].X for t in time_steps}

    for dev in storage:
        res_soc[dev] = {}#{(t): soc[dev][t].X for t in time_steps}
        res_temp_tes = {(t): temp["tes"][t].X for t in time_steps}

    res_p_imp = {(t): p_imp[t].X for t in time_steps}
    res_p_ch = {}
    res_p_dch = {}
    for dev in storage:
        res_p_ch[dev] = {(t): p_ch[dev][t].X for t in time_steps}
        res_p_dch[dev] = {(t): p_dch[dev][t].X for t in time_steps}

    res_gas = {}
    for dev in ["boiler"]:
        res_gas[dev] = {(t): gas[dev][t].X for t in time_steps}

    res_c_dem = {}
    res_c_dem["grid"] = {(t): p_imp[t].X * params["eco"]["pr", "el"] for t in time_steps}

    res_soc_nom = {dev: soc_nom[dev] for dev in storage}

    obj = model.ObjVal
    print("Obj: " + str(model.ObjVal))
    objVal = obj

    runtime = model.getAttr("Runtime")
    datetime.datetime.now()

    # Return results
    return (res_power, res_heat, res_soc,
            res_p_imp, res_p_ch, res_p_dch, obj,
            res_c_dem, res_soc_nom, demand, objVal,
            runtime)



def compute_initial_values(sim_results, par_rh, n_opt):

    init_val = {}
    init_val["soc"] = {}
    # initial SOCs
    for dev in ["tes"]:
        init_val["soc"][dev] = sim_results[3]

    return init_val