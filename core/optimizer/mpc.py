from pathlib import Path
import sys
p = str(Path(__file__).parents[2])
if p not in sys.path:
    sys.path.insert(0, p)
import gurobipy as gp
import os
import json
from pprint import pprint
import pandas as pd
from config.definitions import ROOT_DIR
from core.settings import settings
from core.data_models import Device, Attribute
from core.utils.setup_logger import setup_logger
from core.utils.fiware_utils import clean_up
from requests.exceptions import HTTPError
import traceback
import time


class MPC(Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.n_horizon = settings.N_HORIZON
        self.buildings = self.load_buildings()
        self.mpc_params = self.load_mpc_params()

        self.attr_translation = {
            'electricityDemand': 'elec',
            'heatingDemand': 'heating',
            'coolingDemand': 'cooling',
            'dhwDemand': 'dhw',
            'pvPower': 'pv_power',
        }
        
        self.logger = setup_logger(name=kwargs['entity_id'])
        
        self.attributes = {}
        for name in ['relativePower1',
                     'relativePower2',
                     'relativePower3',
                     'SOCpred1',
                     'SOCpred2',
                     'SOCpred3']:
            self.attributes[name] = Attribute(
                device=self,
                name=name,
                initial_value=None
            )

    @staticmethod
    def load_buildings():
        path = Path(ROOT_DIR) / 'data' / '01_input' / \
            '03_building_devs' / 'Devs.xlsx'

        n_buildings = 5
        building_params = pd.read_excel(path)
        devs = {}
        for n in range(n_buildings):
            devs[n] = {}
            # BOILER
            devs[n]["boi"] = dict(cap=0.0, eta_th=0.97)
            # HEATPUMP
            # TODO: mod_lvl
            devs[n]["hp"] = dict(cap=0.0, dT_max=15, exists=0, mod_lvl=1)
            # ELECTRIC HEATER
            devs[n]["eh"] = dict(cap=0.0)
            # THERMAL ENERGY STORAGE
            # TODO: k_loss
            devs[n]["tes"] = dict(cap=0.0, dT_max=35, min_soc=0.0,
                                  eta_tes=0.98, eta_ch=1, eta_dch=1)

            # Wärmererzeuger und Wärmespeicher
            if building_params["heater"][n] == "boi":
                devs[n]["boi"]["cap"] = building_params["design_heat"][n]
                devs[n]["eh"]["cap"] = building_params["design_dhw"][n]
                devs[n]["tes"]["cap"] = building_params['design_tes'][n]

            elif building_params["heater"][n] == "hp":
                devs[n]["eh"]["cap"] = building_params["design_dhw"][n]
                devs[n]["hp"]["cap"] = building_params["design_heat"][n]
                devs[n]["tes"]["cap"] = building_params['design_tes'][n]

        return devs

    def load_mpc_params(self):
        # TODO put this into json
        param_mpc = {}
        param_mpc["eco"] = {}
        param_mpc["gp"] = {}

        # Always EUR per kWh (meter per anno)
        # €/kWh valid for pv systems with < 10 kWp
        param_mpc["eco"]["sell_pv"] = 0.082
        param_mpc["eco"]["el_grid"] = 0.42
        # Durchschnitt Januar 2023, Quelle Handelsblatt
        param_mpc["eco"]["gas"] = 0.134

        # https://www.gurobi.com/documentation/9.1/refman/mipgap2.html
        param_mpc["gp"]["mip_gap"] = 0.01
        # [s]  https://www.gurobi.com/documentation/9.1/refman/timelimit.html
        param_mpc["gp"]["time_limit"] = 100
        # https://www.gurobi.com/documentation/9.1/refman/numericfocus.html
        param_mpc["gp"]["numeric_focus"] = 3
        return param_mpc

    def get_input_dict_from_fiware(self):
        input_dict = {}
        for building_ix in range(5):
            entity_id = f'BuildingEnergyForecast:DEQ:MVP:{"{:03}".format(building_ix)}'
            attrs = self.cb_client.get_entity_attributes(entity_id=entity_id,
                                                         response_format='keyValues')

            for attr_name, values in attrs.items():
                if attr_name not in self.attr_translation:
                    continue

                translation = self.attr_translation[attr_name]
                if translation not in input_dict:
                    input_dict[translation] = {}

                input_dict[translation][building_ix] = values

        return input_dict

    def get_soc_init(self):
        try:
            ent = self.cb_client.get_entity_attributes(entity_id='ModelicaAgent:DEQ:MVP:000',
                                                       response_format='keyValues')
            soc_init = {'soc': {
                0: {'tes': 0},
                1: {'tes': ent['SOC1']},
                2: {'tes': ent['SOC2']},
                3: {'tes': ent['SOC3']},
                4: {'tes': 0},
            }}
            self.logger.info('Got SOC init from fiware')
            return soc_init
        except HTTPError:
            self.logger.warning('Couldnt get SOC_init, using default')
            return None
            
    def run(self):
        while True:
            _start = time.perf_counter()
            try:
                input_dict = self.get_input_dict_from_fiware()
                self.logger.info('Got input successfully')
            except HTTPError as e:
                error_message = str(e)
                stack_trace = traceback.format_exc()
                self.logger.error(f"OperationalError occurred: {error_message}\nStack Trace:\n{stack_trace}")
                time.sleep(2 - (time.perf_counter() - _start))
                continue
            
            soc_init = self.get_soc_init()
                
            res = self.run_central_optimization(
                demands_and_pv=input_dict,
                n_horizon=self.n_horizon,
                param_mpc=self.mpc_params,
                init_val=soc_init,
                buildings=self.buildings,
                silence=True
            )

            res_power = res[1]
            res_soc = res[3]
            
            self.attributes['relativePower1'].value = res_power[1]['hp'][0] / settings.NORM_POWER
            self.attributes['relativePower2'].value = res_power[2]['hp'][0] / settings.NORM_POWER
            self.attributes['relativePower3'].value = res_power[3]['hp'][0] / settings.NORM_POWER
            self.attributes['SOCpred1'].value = res_soc[1]['tes'][0]
            self.attributes['SOCpred2'].value = res_soc[2]['tes'][0]
            self.attributes['SOCpred3'].value = res_soc[3]['tes'][0]
            
            for attr in self.attributes.values():
                attr.push()
                
            self.logger.info('Pushed all attributes')

            _time = time.perf_counter() - _start
            time.sleep(2-_time)
            
            

    def run_central_optimization(self,
                                 demands_and_pv,
                                 buildings,
                                 n_horizon,
                                 param_mpc,
                                 init_val,
                                 silence=False):
        if not silence:
            return self._run_central_optimization(demands_and_pv=demands_and_pv,
                                                  buildings=buildings,
                                                  n_horizon=n_horizon,
                                                  param_mpc=param_mpc,
                                                  init_val=init_val)
        original_stdout = sys.stdout
        try:
            sys.stdout = open(os.devnull, 'w')
            res = self._run_central_optimization(demands_and_pv=demands_and_pv,
                                                 buildings=buildings,
                                                 n_horizon=n_horizon,
                                                 param_mpc=param_mpc,
                                                 init_val=init_val)
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

        return res

    @staticmethod
    def _run_central_optimization(demands_and_pv,
                                  buildings,
                                  n_horizon,
                                  param_mpc,
                                  init_val):
        # Define subsets
        heater = ("boi", "eh", "hp")
        storage = ("tes",)
        solar = ("pv",)
        device = heater + storage + solar

        model = gp.Model("Design computation")

        N_HORIZON = n_horizon
        DT = 1  # in hours
        time_steps = range(N_HORIZON)

        # Initialization: only if initial values have been generated in previous prediction horizon
        soc_init_rh = {}
        if init_val is not None:
            # initial SOCs
            # Buildings
            for n in buildings:
                soc_init_rh[n] = {}
                for dev in storage:
                    soc_init_rh[n][dev] = init_val["soc"][n][dev]

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
        for n in buildings:
            soc[n] = {}
            p_ch[n] = {}
            p_dch[n] = {}
            for dev in storage:  # All storage devices
                soc[n][dev] = {}
                p_ch[n][dev] = {}
                p_dch[n][dev] = {}
                for t in time_steps:  # All time steps of all days
                    soc[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="SOC_" + dev + "_" + str(t))
                    p_ch[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="P_ch_" + dev + "_" + str(t))
                    p_dch[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="P_dch_" + dev + "_" + str(t))

        for n in buildings:
            power[n] = {}
            heat[n] = {}
            for dev in ["hp", "boi"]:
                power[n][dev] = {}
                heat[n][dev] = {}
                for t in time_steps:
                    power[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="P_" + dev + "_" + str(t))
                    heat[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="Q_" + dev + "_" + str(t))

        cop = {}
        for n in buildings:
            cop[n] = {}
            for dev in ["hp"]:
                cop[n][dev] = {}
                for t in time_steps:
                    cop[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="CoP_" + dev + "_" + str(t))

        for n in buildings:
            for dev in ["eh"]:
                power[n][dev] = {}
                for t in time_steps:
                    power[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="P_" + dev + "_" + str(t))

        for n in buildings:
            for dev in ["pv"]:
                power[n][dev] = {}
                for t in time_steps:
                    power[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="P_" + dev + "_" + str(t))

        # mapping storage sizes
        soc_nom = {}
        for n in buildings:
            soc_nom[n] = {}
            for dev in storage:
                soc_nom[n][dev] = buildings[n][dev]["cap"]
        # Storage initial SOC's
        soc_init = {}
        for n in buildings:
            soc_init[n] = {}
            soc_init[n]["tes"] = soc_nom[n]["tes"] * \
                0.5  # kWh   Initial SOC TES

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
        for n in buildings:
            p_imp[n] = {}
            y_imp[n] = {}
            p_use[n] = {}
            p_sell[n] = {}
            for t in time_steps:
                p_imp[n][t] = model.addVar(
                    vtype="C", lb=0, name="P_imp_" + str(t))
                y_imp[n][t] = model.addVar(
                    vtype="B", lb=0.0, ub=1.0, name="y_imp_exp_" + str(t))
            for dev in ["pv"]:

                p_use[n][dev] = {}
                p_sell[n][dev] = {}
                for t in time_steps:
                    p_use[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="P_use_" + dev + "_" + str(t))
                    p_sell[n][dev][t] = model.addVar(vtype="C", lb=0,
                                                     name="P_sell_" + dev + "_" + str(t))

        # Gas imports to devices
        gas = {}
        for n in buildings:
            gas[n] = {}
            for dev in ["boi"]:

                gas[n][dev] = {}
                for t in time_steps:
                    gas[n][dev][t] = model.addVar(
                        vtype="C", lb=0, name="gas" + dev + "_" + str(t))

        # activation variable for trafo load
        yTrafo = model.addVars(time_steps, vtype="B", name="yTrafo_" + str(t))

        #  BALANCING UNIT VARIABLES

        # Residual network demand
        residual = {}
        residual["demand"] = {}  # Residual network electricity demand
        residual["feed_pv"] = {}  # Residual feed in pv
        power["from_grid"] = {}
        power["to_grid"] = {}
        gas_dom = {}

        for t in time_steps:
            residual["demand"][t] = model.addVar(
                vtype="C", lb=0, name="residual_demand_t" + str(t))
            residual["feed_pv"][t] = model.addVar(
                vtype="C", lb=0, name="residual_feed_pv_t" + str(t))
            power["from_grid"][t] = model.addVar(
                vtype="C", lb=0, name="district_demand_t" + str(t))
            power["to_grid"][t] = model.addVar(
                vtype="C", lb=0, name="district_feed_t" + str(t))
            gas_dom[t] = model.addVar(
                vtype="C", lb=0, name="gas_demand_t" + str(t))

        # Electrical power to/from devices
        for device in ["el_from_grid", "el_to_grid", "gas_from_grid"]:
            power[device] = {}
            for t in time_steps:
                power[device][t] = model.addVar(
                    vtype="C", lb=0, name="power_" + device + "_t" + str(t))

        # total energy amounts taken from grid
        from_grid_total_el = model.addVar(
            vtype="C", lb=0, name="from_grid_total_el")
        # total power to grid
        to_grid_total_el = model.addVar(
            vtype="C", lb=0, name="to_grid_total_el")
        # total gas amounts taken from grid
        from_grid_total_gas = model.addVar(
            vtype="C", lb=0, name="from_grid_total_gas")

        network_load = model.addVar(
            vtype="c", lb=-gp.GRB.INFINITY, name="peak_network_load")

        # Update
        model.update()

        # Objective
        # TODO:
        model.setObjective(c_dem["grid"] + c_dem["gas"] - revenue["grid_pv"]
                           + network_load * 0.01, gp.GRB.MINIMIZE)

        # Network load
        model.addConstrs(
            network_load >= power["from_grid"][t] for t in time_steps)

        for n in buildings:
            for t in time_steps:
                model.addConstr(y_imp[n][t] * 1000 >= p_imp[n]
                                [t], name="Max_el_imp_" + str(t))
                # model.addConstr((1 - y_imp[n][t]) * 1000 >= p_sell[n]["pv"][t] + p_sell[n]["CHP"][t],
                #                 name="Max_el_exp_" + str(t))
                model.addConstr((1 - y_imp[n][t]) * 1000 >= p_sell[n]["pv"][t],
                                name="Max_el_exp_" + str(t))

        # Define constraints

        # Economic constraints

        # Demand related costs (gas)
        model.addConstr(
            c_dem["gas"] == param_mpc["eco"]["gas"] *
            sum(DT * gas_dom[t] for t in time_steps),
            name="Demand_costs_gas")
        # Demand related costs (electricity)
        model.addConstr(
            c_dem["grid"] == param_mpc["eco"]["el_grid"] * sum(
                DT * residual["demand"][t] for t in time_steps),
            name="Demand_costs_el_grid")
        # Revenues for selling electricity to the grid / neighborhood
        model.addConstr(
            revenue["grid_pv"] == param_mpc["eco"]["sell_pv"] * sum(
                DT * residual["feed_pv"][t] for t in time_steps),
            name="Feed_in_rev_pv")

        # Technical constraints

        # Determine nominal heat at every timestep
        for n in buildings:
            for t in time_steps:
                for dev in ["hp", "boi", "eh"]:
                    # for dev in ["hp35", "hp55", "chp", "boi", "eh"]:

                    if dev == "eh":
                        model.addConstr(power[n][dev][t] <=
                                        buildings[n][dev]["cap"])
                    else:
                        model.addConstr(heat[n][dev][t] <= buildings[n][dev]["cap"],
                                        name="Max_heat_operation_" + dev)

        # Devices operation
        # Heat output between mod_lvl*Q_nom and Q_nom (P_nom for heat pumps)
        # Power and Energy directly result from Heat output
        for n in buildings:
            for t in time_steps:
                # Heatpumps
                dev = "hp"
                model.addConstr(heat[n][dev][t] == power[n][dev][t] * cop[n][dev][t],
                                name="Power_equation_" + dev + "_" + str(t))

                # model.addConstr(cop[n][dev][t] == 0.4 * (273.15 + 35) / (35 - T_air[t]),
                #                 name="CoP_equation_" + dev + "_" + str(t))
                model.addConstr(cop[n][dev][t] == 0.4 * (273.15 + 35) / (35 - 5),
                                name="CoP_equation_" + dev + "_" + str(t))

                # BOILER
                dev = "boi"
                model.addConstr(
                    heat[n]["boi"][t] == buildings[n]["boi"]["eta_th"] *
                    gas[n]["boi"][t],
                    name="Power_equation_" + dev + "_" + str(t))

        # # Solar components
        for n in buildings:
            for dev in solar:
                for t in time_steps:
                    model.addConstr(power[n][dev][t] == demands_and_pv["pv_power"][n][t],
                                    name="Solar_electrical_" + dev + "_" + str(t))

        # power of the electric heater
        for n in buildings:
            # eletric heater covers 50% of the dhw
            for t in time_steps:
                if buildings[n]["eh"]["cap"] == 0.0:
                    model.addConstr(power[n]["eh"][t] == 0,
                                    name="El_heater_act_" + str(t))
                else:
                    model.addConstr(power[n]["eh"][t] == 0.5 * demands_and_pv["dhw"][n][t],
                                    name="El_heater_act_" + str(t))

        #  BUILDING STORAGES # %% DOMESTIC FLEXIBILITIES

        # TES CONSTRAINTS CONSTRAINTS
        dev = "tes"
        for n in buildings:
            eta_tes = buildings[n][dev]["eta_tes"]
            eta_ch = buildings[n][dev]["eta_ch"]
            eta_dch = buildings[n][dev]["eta_dch"]

            for t in time_steps:
                # Initial SOC is the SOC at the beginning of the first time step, thus it equals the SOC at the end of the previous time step
                if t == 0:
                    try:
                        soc_prev = soc_init_rh[n][dev]
                    except KeyError:
                        soc_prev = soc_init[n][dev]
                else:
                    soc_prev = soc[n][dev][t - 1]

                # Maximal charging
                model.addConstr(p_ch[n][dev][t] == eta_ch * (heat[n]["hp"][t] + heat[n]["boi"][t]),
                                name="Heat_charging_" + str(t))
                # Maximal discharging
                if buildings[n]["eh"]["cap"] == 0.0:
                    model.addConstr(p_dch[n][dev][t] == (1 / eta_dch) * (
                        demands_and_pv["heating"][n][t] + demands_and_pv["dhw"][n][t]),
                        name="Heat_discharging_" + str(t))
                else:
                    model.addConstr(p_dch[n][dev][t] == (1 / eta_dch) * (
                        demands_and_pv["heating"][n][t] + 0.5 * demands_and_pv["dhw"][n][t]),
                        name="Heat_discharging_" + str(t))

                # Minimal and maximal soc
                # model.addConstr(soc[n]["TES"][t] <= soc_nom[n]["TES"], name="max_cap_tes_" + str(t))
                # model.addConstr(soc[n]["TES"][t] >= nodes[n]["buildings"]["TES"]["min_soc"] * soc_nom[n]["TES"],
                #                name="min_cap_" + str(t))

                # SOC coupled over all times steps (Energy amount balance, kWh)
                model.addConstr(
                    soc[n][dev][t] == soc_prev * eta_tes + DT *
                    (p_ch[n][dev][t] - p_dch[n][dev][t]),
                    name="Storage_bal_" + dev + "_" + str(t))

            # TODO: soc at the end is the same like at the beginning
            # if t == last_time_step:
            #    model.addConstr(soc[device][t] == soc_init[device],
            #                    name="End_TES_Storage_" + str(t))

        # Electricity balance (house)
        for n in buildings:
            for t in time_steps:
                model.addConstr(demands_and_pv["elec"][n][t]
                                + power[n]["hp"][t] + power[n]["eh"][t]
                                - p_use[n]["pv"][t]
                                == p_imp[n][t],
                                name="Electricity_balance_" + str(t))

        # Split CHP and PV generation into self-consumed and sold powers
        # for n in buildings:
        #     for dev in ("pv",):
        #         for t in time_steps:
        #             model.addConstr(p_sell[n][dev][t] + p_use[n][dev][t] == power[n][dev][t],
        #                             name="power=sell+use_" + dev + "_" + str(t))

        # energy balance neighborhood

        # Residual loads
        for t in time_steps:
            # Residual network electricity demand (Power balance, MW)
            model.addConstr(residual["demand"][t] == sum(
                p_imp[n][t] for n in buildings))
            model.addConstr(residual["feed_pv"][t] == sum(
                p_sell[n]["pv"][t] for n in buildings))
            # Gas balance (power)
            model.addConstr(gas_dom[t] == sum(gas[n]["boi"][t] for n in buildings),
                            name="Demand_gas_total")

        # Total gas amounts taken from grid (Energy amounts, MWh)
        model.addConstr(
            from_grid_total_gas == sum(DT * power["gas_from_grid"][t] for t in time_steps))
        # Total electricity amounts taken from grid (Energy amounts, MWh)
        model.addConstr(from_grid_total_el == sum(
            DT * power["from_grid"][t] for t in time_steps))
        # Total electricity feed-in (Energy amounts, MWh)
        model.addConstr(to_grid_total_el == sum(
            DT * power["to_grid"][t] for t in time_steps))

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
                    print(c.constrName)
                    f.write('%s' % c.constrName)
                    f.write('\n')
                    IISconstr.append(c.constrName)
            f.close()
        model.update()

        # Retrieve results
        t = 0
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
        for n in buildings:
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
            res_y[n] = [y_imp[n][t].X for t in time_steps]
            for dev in ["hp", "boi"]:
                res_power[n][dev] = [power[n][dev][t].X for t in time_steps]
                res_heat[n][dev] = [heat[n][dev][t].X for t in time_steps]
            for dev in ["pv"]:
                res_power[n][dev] = [power[n][dev][t].X for t in time_steps]
            for dev in storage:
                res_soc[n][dev] = [soc[n][dev][t].X for t in time_steps]
            for dev in storage:
                res_p_ch[n][dev] = [p_ch[n][dev][t].X for t in time_steps]
                res_p_dch[n][dev] = [p_dch[n][dev][t].X for t in time_steps]
            for dev in ["boi"]:
                res_gas[n][dev] = [gas[n][dev][t].X for t in time_steps]

            res_c_dem[n]["c_gas"] = [param_mpc["eco"]["gas"]
                                     * gas[n]["boi"][t].X for t in time_steps]
            res_c_dem[n]["house_c_dem"] = [p_imp[n][t].X *
                                           param_mpc["eco"]["el_grid"] for t in time_steps]
            res_rev[n]["house_rev"] = [p_sell[n]["pv"][t].X *
                                       param_mpc["eco"]["sell_pv"] for t in time_steps]

            res_soc_nom[n] = {dev: soc_nom[n][dev] for dev in storage}
            for dev in ("pv",):
                res_p_use[n][dev] = [p_use[n][dev][t].X for t in time_steps]
                res_p_sell[n][dev] = [p_sell[n][dev][t].X for t in time_steps]
            res_p_imp[n] = [p_imp[n][t].X for t in time_steps]

        res_c_dem["ONT_c_dem"] = [power["from_grid"][t].X *
                                  param_mpc["eco"]["el_grid"] for t in time_steps]

        res_p_to_grid = [power["to_grid"][t].X for t in time_steps]
        res_p_from_grid = [power["from_grid"][t].X for t in time_steps]
        res_gas_from_grid = [gas_dom[t].X for t in time_steps]
        res_p_feed_pv = [residual["feed_pv"][t].X for t in time_steps]
        res_p_demand = [residual["demand"][t].X for t in time_steps]

        # obj = model.ObjVal
        # print("Obj: " + str(model.ObjVal))

        # Return results
        return (res_y, res_power, res_heat, res_soc, res_p_imp,
                res_p_ch, res_p_dch, res_p_use, res_p_sell, res_gas,
                res_c_dem, res_rev,
                res_p_to_grid, res_p_from_grid,
                res_gas_from_grid, res_p_feed_pv, res_p_demand)


if __name__ == '__main__':
    #clean_up()
    schema_path = Path(__file__).parents[1] / 'data_models' /\
        'schema' / 'MPC.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    mpc = MPC(
        entity_id='MPC:DEQ:MVP:000',
        entity_type='MPC',
        data_model=data_model,
        save_history=True        
    )
    mpc.run()
