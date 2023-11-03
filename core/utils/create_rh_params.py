import numpy as np

def create_rh_params():
    # Set rolling horizon options
    # TODO: options rh into json input file
    param_rh = {
        # Parameters for operational optimization
        "n_hours": 36,  # ----,      number of hours of prediction horizon for rolling horizon
        "n_hours_ov": 35,  # ----,      number of hours of overlap horizon for rolling horizon
        "n_opt_max": 8760,  # 8760  # -----,       maximum number of optimizations
        "month": 0,  # -----,     optimize this month 1-12 (1: Jan, 2: Feb, ...), set to 0 to optimize entire year
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
    # param_rh["datapoints"] = int(8760 / options["discretization_input_data"])
    param_rh["datapoints"] = 8760

    return param_rh