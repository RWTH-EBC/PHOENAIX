from core.utils.load_demands import load_demands_and_pv
import matplotlib.pyplot as plt
from enstats.clustering.clustering_optimizer.system_identification \
    .one_step_optimization import OneStepOptimizationFROLS
from ebcpy.data_types import TimeSeriesData as Tsd
import pandas as pd
import numpy as np
from pprint import pprint
from sampc.utils.multi_step_runner import calc_multi_step_error
from sampc.utils.utils import get_output_position_change
from enstats.preprocessing.utils import tsd_preparation_from_feature_list
from sklearn.metrics import mean_squared_error as mse
from sampc.utils.multi_step_runner import runner_segment_y
import numpy as np
import warnings


class HeatingDemandLearner:
    def __init__(self,
                 building_ix: int) -> None:

        self.building_ix = building_ix
        self.model_dict = None
        self.n_step_error = None

    def get_model(self,
                  train_test: float = 0.7,
                  n_horizon: int = 12):

        self.output_variables = [(f'heating_{self.building_ix}', 'raw')]
        base_features = [('ones', 'raw'), ('sin', 'raw')]

        self.use_data = self._get_data()
        self.n_horizon = n_horizon
        self.train_model(use_data=self.use_data,
                         output_variables=self.output_variables,
                         features=base_features,
                         train_test=train_test,
                         n_horizon=n_horizon)

    def _get_data(self):
        # TODO hardcoded to go to 1 hour intervals
        data = load_demands_and_pv().iloc[::4].copy()
        new_cols = [f'{i[0]}_{i[1]}' for i in list(data)]
        data_new = pd.DataFrame(columns=new_cols, data=data.to_numpy())
        tsd = Tsd(data_new)

        imp_cols = [i for i in list(tsd) if f'_{self.building_ix}' in i[0]]
        use_data = data_new[imp_cols].copy()

        hours = data.index.hour + data.index.minute / 60
        B = 2 * np.pi / 24
        C = -np.pi / 2
        use_data[('sin', 'raw')] = np.sin(B * hours + C)
        use_data[('time', 'raw')] = data.index
        use_data[('Class', 'constant')] = 0
        use_data[('ones', 'raw')] = 1

        return use_data

    def train_model(self,
                    use_data,
                    output_variables,
                    features,
                    train_test,
                    n_horizon):

        lowest_error = np.inf
        best_model = None
        for scaling in ['minmax', 'norm', 'standard']:
            (error,
             model_dict) = self._train_model(use_data,
                                             output_variables,
                                             features,
                                             train_test,
                                             scaling,
                                             n_horizon)
            if error < lowest_error:
                lowest_error = error
                best_model = model_dict

        self.model_dict = best_model
        self.features = self.model_dict['features']
        self.coeffs = self.model_dict['coeffs']
        self.out_pos = get_output_position_change(feature_list=self.features,
                                                  output_variables=self.output_variables)
        self.n_step_error = lowest_error
        self.run_data = tsd_preparation_from_feature_list(
            self.use_data, self.features)

    def predict(self):
        pass

    def _train_model(self,
                     use_data,
                     output_variables,
                     features,
                     train_test,
                     scaling,
                     n_horizon):
        opt = OneStepOptimizationFROLS(data=use_data,
                                       output_variables=output_variables,
                                       input_variables=features,
                                       environment_variables=None,
                                       class_column=('Class', 'constant'),
                                       train_test=train_test,
                                       scaling_method=scaling,
                                       verbose=False,
                                       compare_with_no_ode=False
                                       )
        opt.optimize()

        inv_scaled_dict = opt.get_inverse_scaled_results()[0]['result']
        features = inv_scaled_dict['features']
        coeffs = inv_scaled_dict['coeffs']

        run_data = tsd_preparation_from_feature_list(use_data, features)

        X = run_data[features].to_numpy()
        y = run_data[output_variables].to_numpy()

        out_pos = get_output_position_change(feature_list=features,
                                             output_variables=output_variables)

        x_list = [X]
        y_list = [y]

        error = calc_multi_step_error(x_list=x_list,
                                      y_list=y_list,
                                      out_is_dt=False,
                                      scaling_dict=None,
                                      coeffs=coeffs,
                                      pos_change=out_pos,
                                      n_horizon=n_horizon,
                                      return_arrays=False)

        return (error, inv_scaled_dict)

    def run_and_plot_single_step(self):
        if self.model_dict is None:
            warnings.warn('No model trained yet')
            return

        X = self.run_data[self.features].to_numpy()
        y = self.run_data[self.output_variables].to_numpy()

        y_pred = X @ self.coeffs.T

        rmse = mse(y_pred, y) ** 0.5
        plt.figure(figsize=(16, 9))
        plt.plot(y, label='real')
        plt.plot(y_pred, label='sim')
        plt.legend()
        plt.title(f'RMSE: {rmse}')
        plt.show()

    def run_and_plot_multi_step(self,
                                n_horizon: int = 12):
        if self.model_dict is None:
            warnings.warn('No model trained yet')
            return

        features = self.model_dict['features']
        coeffs = self.model_dict['coeffs']

        X = self.run_data[self.features].to_numpy()
        y = self.run_data[self.output_variables].to_numpy()

        x_list = [X]
        y_list = [y]
        (error,
         _y_arrays,
         _y_pred_array) = calc_multi_step_error(x_list=x_list,
                                                y_list=y_list,
                                                out_is_dt=False,
                                                scaling_dict=None,
                                                coeffs=coeffs,
                                                pos_change=self.out_pos,
                                                n_horizon=n_horizon,
                                                return_arrays=True)

        y_pred_arrays = _y_pred_array[0]
        y_pred_all = y_pred_arrays[::n_horizon]
        n_points = y_pred_all.shape[0] * y_pred_all.shape[1]
        y_pred_flatten = y_pred_all.reshape(1, n_points).flatten()

        y = y[:y_pred_flatten.shape[0]]

        plt.figure(figsize=(16, 9))
        plt.plot(y, label='real')
        ix_start = 0
        for n, _y in enumerate(y_pred_all):
            x = np.arange(start=ix_start, stop=ix_start + _y.shape[0])
            ix_start = x[-1] + 1

            if n == 0:
                plt.plot(x, _y, c='orange', label='pred')
            else:
                plt.plot(x, _y, c='orange')

        rmse = mse(y_pred_flatten, y) ** 0.5
        plt.legend()
        plt.title(f'RMSE: {rmse}')
        plt.show()

    @staticmethod
    def data_shifter(data):
        shift_dict = {}

        for col in list(data):
            _col, tag = col

            if '//' in _col:
                name, shift = _col.split('//')

            else:
                name = _col
                shift = 0

            if any(i in name for i in ['sin', 'ones']):
                continue
            
            if name not in shift_dict:
                shift_dict[name] = []

            shift_dict[name].append((col, int(shift)))

        for key, val in shift_dict.items():
            shift_dict[key] = sorted(val, key=lambda x: x[1])

        for name, shift_vars in shift_dict.items():
            use_shift_vars = [i[0] for i in shift_vars]
            this_data = data.loc[0, use_shift_vars].to_numpy()
            n = this_data.shape[0]
            matrix = np.full((n, n), np.nan)

            for i in range(n):
                matrix[i, i:n] = this_data[0: n-i]

            data.loc[0: n-1, use_shift_vars] = matrix

        return data
    
    @staticmethod
    def sin_extension(tsd,
                      n_horizon):
        
        def apply_sin_calc(x):
            try: 
                b = 2 * np.pi / 24
                c = -np.pi / 2
                return np.sin(b * x + c)
            except:
                print(x)
                return x

        assert (tsd.shape[0] == 1)
        
        new_rows = pd.DataFrame(np.nan, index=range(n_horizon - 1), columns=tsd.columns)
        df = pd.concat([tsd, new_rows], ignore_index=True)
        sin_cols = [i for i in list(df) if 'sin' in i[0]]

        for i in range(1, len(df)):
            df.loc[df.index[i], sin_cols] = (df.loc[df.index[i-1], sin_cols] + 1) % 24
        
        
        df[sin_cols] = df[sin_cols].apply(apply_sin_calc)
        if ('ones', 'raw') in list(df):
            df[('ones', 'raw')] = 1
            
        return df

    def predict_n_steps(self,
                        input_tsd):
        input_tsd = self.sin_extension(tsd=input_tsd,
                                       n_horizon=self.n_horizon)
        
        if input_tsd.shape[0] != self.n_horizon:
            warnings.warn(f'The input tsd has {input_tsd.shape[0]} rows, but your n_horizon is {self.n_horizon}')
        
        input_tsd = self.data_shifter(input_tsd)
        u_array = input_tsd[self.features].to_numpy()
        y_array = np.full((u_array.shape[0], 1), np.nan)

        y_hat = runner_segment_y(y_array=y_array,
                                 u_array=u_array,
                                 w=self.coeffs,
                                 pos_change=self.out_pos)
        
        return y_hat
