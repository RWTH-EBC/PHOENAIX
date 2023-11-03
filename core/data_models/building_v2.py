from core.data_models import Device
import time
import threading
import random


class Building(Device):
    def __init__(self, *args, **kwargs):

        # setup entity type (fix the entity type)
        self.entity_type = "Building"
        self.mpc = MPC()

    def map_devices_opti(self):

        devs = {}
        # number of buildings
        for n in range(options["nb_bes"]):
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
            devs[n]["tes"] = dict(cap=0.0, dT_max=35, min_soc=0.0, eta_tes=0.98, eta_ch=1, eta_dch=1)

        # load building parameter
        # TODO: add csv file with building parameter
        # Joel sends csv
        building_params = pd.read_csv(options["path_input"] + "building_params" + ".csv", delimiter=";")

        # Wärmererzeuger und Wärmespeicher
        if building_params["heater"][n] == "boi":
            devs[n]["boi"]["cap"] = building_params["design_heat"][n]
            devs[n]["devs"]["EH"]["cap"] = building_params["design_dhw"][n]
            devs[n]["devs"]["TES"]["cap"] = building_params['design_tes'][n]

        elif building_params["heater"][n] == "hp":
            devs[n]["devs"]["EH"]["cap"] = building_params["design_dhw"][n]
            devs[n]["devs"]["HP"]["cap"] = building_params["design_heat"][n]
            devs[n]["devs"]["TES"]["cap"] =building_params['design_tes'][n]


    def fmu_import(self):

    def fmu_initialization(self):

    def run_mpc(self):

        #TODO: get param_mpc, param_rh, devs
        #TODO: fmu import and initialization

        # Run rolling horizon
        init_val = {}  # not needed for first optimization, thus empty dictionary
        opti_res = {}  # to store the results of the bes optimization
        # Start optimizations
        for n_opt in range(par_rh["n_opt"]):
            opti_res[n_opt] = {}
            init_val[0] = {}
            init_val[n_opt+1] = {}

            #TODO: get forecast demands and weather

            if n_opt == 0:
                print("Starting optimization: n_opt: " + str(n_opt) + ".")
                init_val[n_opt] = {}
                opti_res[n_opt] = run_central_optimization(demands_forecast, devs, weather_forecast, param_mpc,
                                                           param_rh, init_val, n_opt)
                #TODO: into run_central_optimization
                #TODO: run fmu
                init_val[n_opt + 1] = init_val_central_operation(opti_res[n_opt], nodes, par_rh, n_opt)
            else:
                print("Starting optimization: n_opt: " + str(n_opt) + ".")
                opti_res[n_opt] = run_central_optimization(demands_forecast, devs, weather_forecast, param_mpc,
                                                           param_rh, init_val, n_opt)
                # TODO: into run_central_optimization
                # TODO: run fmu
                # init val gets storage load of buildings
                init_val[n_opt + 1] = init_val_central_operation(opti_res[n_opt], nodes, par_rh, n_opt)
            print("Finished optimization " + str(n_opt) + ". " + str((n_opt + 1) / par_rh["n_opt"] * 100) + "% of optimizations processed.")
        # opti res returns hp power for buildings with heat pump
        return opti_res








if __name__ == '__main__':
    MPC = MPC(entity_id="MPC:01")

