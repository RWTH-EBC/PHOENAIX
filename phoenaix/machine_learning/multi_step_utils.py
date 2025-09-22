import numpy as np
from numba import njit
from enstats.clustering.clustering_optimizer.system_identification.\
    sampc_scaling import _get_params
from enstats.utils.utils import get_base_var


def calc_multi_step_error(x_list,
                          y_list,
                          out_is_dt,
                          scaling_dict,
                          coeffs,
                          pos_change,
                          n_horizon,
                          return_arrays=False):
    if scaling_dict is None:
        x_div = x_minus = y_div = y_minus = None

    else:
        x_div, x_minus, y_div, y_minus = _get_params(scaling_dict)

    multi_step_rmse_adder = 0
    n_points = 0
    
    y_arrays_list = []
    y_pred_arrays_list = []

    for n in range(len(x_list)):
        u_array = x_list[n]
        y_array = y_list[n]

        if scaling_dict is None:
            (rmse_ix,
             y_arrays,
             y_pred_arrays) = n_step_rmse(y_array,
                                  u_array,
                                  coeffs,
                                  pos_change,
                                  n_horizon,
                                  out_is_dt)

        else:
            (rmse_ix,
             y_arrays,
             y_pred_arrays) = n_step_rmse_sc(y_array,
                                     u_array,
                                     coeffs,
                                     pos_change,
                                     n_horizon,
                                     x_div,
                                     x_minus,
                                     y_div,
                                     y_minus,
                                     out_is_dt)

        n_ix = y_array.shape[0]

        multi_step_rmse_adder += rmse_ix * n_ix
        n_points += n_ix
        
        y_arrays_list.append(y_arrays)
        y_pred_arrays_list.append(y_pred_arrays)

    multi_step_rmse = multi_step_rmse_adder / n_points
    
    if return_arrays:
        return (multi_step_rmse,
                y_arrays_list,
                y_pred_arrays_list)
    return multi_step_rmse


@njit
def n_step_rmse(y_array,
                u_array,
                w,
                pos_change,
                steps_ahead,
                out_is_dt=False):
    n_y = y_array.shape[0]
    if steps_ahead > n_y:
        steps_ahead = n_y

    n_calc_rounds = n_y - steps_ahead + 1
    rmse_array = np.full((n_calc_rounds,), np.nan)
    y_arrays = np.full((n_calc_rounds, steps_ahead), np.nan)
    y_pred_arrays = np.full((n_calc_rounds, steps_ahead), np.nan)
    

    for n_round in range(n_calc_rounds):

        if out_is_dt:
            yhat_temp = runner_segment_dy(
                y_array[n_round: n_round + steps_ahead],
                u_array[n_round: n_round + steps_ahead],
                w,
                pos_change,
            )
        else:
            yhat_temp = runner_segment_y(
                y_array[n_round: n_round + steps_ahead],
                u_array[n_round: n_round + steps_ahead],
                w,
                pos_change,
            )

        y_comp = y_array[n_round: n_round + steps_ahead]

        rmse = (np.sum((yhat_temp - y_comp) ** 2, axis=0) /
                y_comp.shape[0]) ** 0.5
        rmse_array[n_round] = rmse[0]
        
        y_arrays[n_round, :] = y_comp.flatten()
        y_pred_arrays[n_round, :] = yhat_temp.flatten()

    rmse_mean = np.mean(rmse_array)

    return (rmse_mean,
            y_arrays,
            y_pred_arrays)


@njit
def n_step_rmse_sc(y_array,
                   u_array,
                   w,
                   pos_change,
                   steps_ahead,
                   x_div,
                   x_minus,
                   y_div,
                   y_minus,
                   out_is_dt=False):
    n_y = y_array.shape[0]
    if steps_ahead > n_y:
        steps_ahead = n_y

    n_calc_rounds = n_y - steps_ahead + 1
    rmse_array = np.full((n_calc_rounds,), np.nan)
    y_arrays = np.full((n_calc_rounds, steps_ahead), np.nan)
    y_pred_arrays = np.full((n_calc_rounds, steps_ahead), np.nan)

    for n_round in range(n_calc_rounds):

        if out_is_dt:
            yhat_temp = runner_segment_dy_sc(
                y_array[n_round: n_round + steps_ahead],
                u_array[n_round: n_round + steps_ahead],
                w,
                pos_change,
                x_div,
                x_minus,
                y_div,
                y_minus
            )
        else:
            yhat_temp = runner_segment_y_sc(
                y_array[n_round: n_round + steps_ahead],
                u_array[n_round: n_round + steps_ahead],
                w,
                pos_change,
                x_div,
                x_minus,
                y_div,
                y_minus
            )

        y_comp = y_array[n_round: n_round + steps_ahead]

        rmse = (np.sum((yhat_temp - y_comp) ** 2, axis=0) /
                y_comp.shape[0]) ** 0.5
        rmse_array[n_round] = rmse[0]
        
        y_arrays[n_round, :] = y_comp
        y_pred_arrays[n_round, :] = yhat_temp

    rmse_mean = np.mean(rmse_array)

    return (rmse_mean,
            y_arrays,
            y_pred_arrays)
    
@njit
def runner_segment_y(y_array,
                     u_array,
                     w,
                     pos_change):
    y_calc_array = np.full(
        y_array.shape, np.nan
    )

    for n in range(y_array.shape[0]):
        u_new = u_array[n].copy().astype(np.float64)

        for p_c in pos_change:
            pos, pos_shift = p_c
            if pos == -1:
                continue

            if n - pos_shift < 0:
                continue

            u_new[pos] = y_calc_array[n-pos_shift, 0]

        y_calc_array[n] = u_new @ w.T

    return y_calc_array


@njit
def runner_segment_dy(y_array,
                      u_array,
                      w,
                      pos_change):
    y_calc_array = np.full(
        y_array.shape, np.nan
    )

    y_calc_array[0] = y_array[0]

    for n in range(y_array.shape[0]-1):
        u_new = u_array[n].copy().astype(np.float64)

        for p_c in pos_change:
            pos, pos_shift = p_c
            if pos == -1:
                continue

            if n - pos_shift < 0:
                continue

            u_new[pos] = y_calc_array[n - pos_shift, 0]

        y_calc_array[n+1] = (u_new @ w.T) + y_calc_array[n]

    return y_calc_array

@njit
def runner_segment_y_sc(y_array,
                        u_array,
                        w,
                        pos_change,
                        x_div,
                        x_minus,
                        y_div,
                        y_minus
                        ):
    y_calc_array = np.full(
        y_array.shape, np.nan
    )

    for n in range(y_array.shape[0]):
        u_new = u_array[n].copy().astype(np.float64)

        for p_c in pos_change:
            pos, pos_shift = p_c
            if pos == -1:
                continue

            if n - pos_shift < 0:
                continue
            u_new[pos] = y_calc_array[n-pos_shift, 0]

        u_new_sc = (u_new - x_minus) / x_div
        y_calc_sc = u_new_sc @ w.T
        y_calc = (y_calc_sc * y_div) + y_minus
        y_calc_array[n] = y_calc

    return y_calc_array


@njit
def runner_segment_dy_sc(y_array,
                         u_array,
                         w,
                         pos_change,
                         x_div,
                         x_minus,
                         y_div,
                         y_minus
                         ):
    y_calc_array = np.full(
        y_array.shape, np.nan
    )

    y_calc_array[0] = y_array[0]

    for n in range(y_array.shape[0]-1):
        u_new = u_array[n].copy().astype(np.float64)

        for p_c in pos_change:
            pos, pos_shift = p_c
            if pos == -1:
                continue

            if n - pos_shift < 0:
                continue

            u_new[pos] = y_calc_array[n - pos_shift, 0]

        u_new_sc = (u_new - x_minus) / x_div
        dy_calc_sc = u_new_sc @ w.T

        dy_calc = (dy_calc_sc * y_div) + y_minus

        y_calc_array[n+1] = dy_calc + y_calc_array[n]

    return y_calc_array

def get_output_position_change(feature_list,
                               output_variables):
    output_variables = [get_base_var(i)[0] for i in output_variables]
    out_positions = []
    for n, i in enumerate(feature_list):

        base_var, lag = get_base_var(i)
        if base_var in output_variables:
            out_positions.append((n, lag))

    if len(out_positions) == 0:
        out_positions = np.array([[-1, -1]])
    else:
        out_positions = np.array(out_positions)

    return out_positions