import copy
import shutil

import fmpy
import fmpy.fmi2


class FMUHandler:
    """
    The fmu handler class
    """

    def __init__(self,
                 fmu_path,
                 step_size,
                 tolerance=0.0001,
                 use_local=False,
                 init_values=None):
        self.fmu_path = fmu_path
        self.step_size = step_size
        self.use_local = use_local
        self.tolerance = tolerance

        self.model_description = None
        self.variables = {}
        self.unzipdir = None
        self.fmu = None
        self.fmu_state = None

        self.current_time = 0
        self.init_values = init_values

    def initialize(self):
        self.fmu_state = None
        if self.unzipdir is not None:
            self.terminate_and_free_instance()

        # read the model description
        self.model_description = fmpy.read_model_description(self.fmu_path)

        # Collect all variables
        self.variables = {}
        for variable in self.model_description.modelVariables:
            self.variables[variable.name] = variable

        # extract the FMU
        self.unzipdir = fmpy.extract(self.fmu_path)

        # create fmu obj
        self.fmu = fmpy.fmi2.FMU2Slave(guid=self.model_description.guid,
                                       unzipDirectory=self.unzipdir,
                                       modelIdentifier=self.model_description.coSimulation.modelIdentifier,
                                       instanceName=__name__)

        # instantiate fmu
        self.fmu.instantiate()
        self.fmu.setupExperiment(startTime=0,
                                 tolerance=self.tolerance)

        self.fmu.enterInitializationMode()
        self.fmu.exitInitializationMode()

        if self.init_values is not None:
            self.set_values(self.init_values)
            print('Values set')

    def find_vars(self, find_str: (str, list), exclude_str: (str, list) = None):
        """
        Retruns all variables with given substring
        """
        if isinstance(find_str, str):
            find_str = [find_str]

        if exclude_str is None:
            exclude_str = []

        if isinstance(exclude_str, str):
            exclude_str = [exclude_str]
        key = list(self.variables.keys())
        key_list = []
        for i in range(len(key)):
            all_included = all(j in key[i] for j in find_str)
            any_excluded = any(j in key[i] for j in exclude_str)
            if all_included and not any_excluded:
                key_list.append(key[i])

        return key_list

    def find_vars_end(self, end_str: str):
        """
        Retruns all variables ending with start_str
        """
        key = list(self.variables.keys())
        key_list = []
        for i in range(len(key)):
            if key[i].endswith(end_str):
                key_list.append(key[i])
        return key_list

    def get_value(self, var_name: str):
        """
        Get a single variable.
        """

        variable = self.variables[var_name]
        vr = [variable.valueReference]

        if variable.type == 'Real':
            return self.fmu.getReal(vr)[0]
        elif variable.type in ['Integer', 'Enumeration']:
            return self.fmu.getInteger(vr)[0]
        elif variable.type == 'Boolean':
            value = self.fmu.getBoolean(vr)[0]
            return value != 0
        else:
            raise Exception("Unsupported type: %s" % variable.type)

    def set_values(self, var_val_dict):
        if var_val_dict is None:
            return
        for var, val in var_val_dict.items():
            self.set_value(var, val)

    def set_value(self, var_name, value):
        """
        Set a single variable.
        var_name: str
        """
        if value is None:
            return

        variable = self.variables[var_name]
        vr = [variable.valueReference]

        if variable.type == 'Real':
            self.fmu.setReal(vr, [float(value)])
        elif variable.type in ['Integer', 'Enumeration']:
            self.fmu.setInteger(vr, [int(value)])
        elif variable.type == 'Boolean':
            self.fmu.setBoolean(vr, [value == 1.0 or value == True or value == "True"])
        else:
            raise Exception("Unsupported type: %s" % variable.type)

    def do_step(self, set_var_dict):
        if not self.use_local and self.fmu_state is not None:
            fmu_state = self.fmu.deserializeFMUState(self.fmu_state)
            self.fmu.setFMUState(fmu_state)
            self.fmu.freeFMUState(fmu_state)

        self.set_values(set_var_dict)
        self.fmu.doStep(
            currentCommunicationPoint=self.current_time,
            communicationStepSize=self.step_size)
        # augment current time step

        if not self.use_local:
            fmu_state = copy.deepcopy(self.fmu.serializeFMUstate(self.fmu.getFMUState()))
        else:
            fmu_state = None
        return fmu_state

    def terminate_and_free_instance(self):
        self.fmu.terminate()
        self.fmu.freeInstance()
        shutil.rmtree(self.unzipdir, ignore_errors=True)

    def read_variables(self, vrs_list: list):
        """
        Reads multiple variable values of FMU.
        vrs_list as list of strings
        Method retruns a dict with FMU variable names as key
        """
        res = {}
        # read current variable values ans store in dict
        for var in vrs_list:
            res[var] = self.get_value(var)

        # add current time to results
        res['SimTime'] = self.current_time

        return res

    def set_variables(self, var_dict: dict):
        '''
        Sets multiple variables.
        var_dict is a dict with variable names in keys.
        '''

        for key in var_dict:
            self.set_value(key, var_dict[key])
        return "Variable set!!"

    def __enter__(self):
        self.fmu.terminate()
        self.fmu.freeInstance()
