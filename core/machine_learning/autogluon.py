import pandas as pd
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
from forecast_base_model import ForecastBaseModel


class AutoGluonForecaster(ForecastBaseModel):
    def __init__(self):
        self.predictor = None
        self.forecast = None
        self.item_id_name = "item_id"
        self.item_id = "case1"

    def train_model(self, training_data:pd.DataFrame, prediction_horizon:int):

        training_data[self.item_id_name] = self.item_id
        train_data_autogluon = TimeSeriesDataFrame.from_data_frame(
            training_data,
            id_column=self.item_id_name,
            timestamp_column="timestamp"
        )


        predictor = TimeSeriesPredictor(
            prediction_length=prediction_horizon,
            path="autogluon-trial1",
            target="target",
            eval_metric="MASE",
        )

        predictor.fit(
            train_data_autogluon,
            presets="fast_training",
            time_limit=30,
        )

        self.predictor = predictor

    def predict_model(self, past_data:pd.DataFrame):

        past_data = TimeSeriesDataFrame.from_data_frame(
            past_data,
            id_column=self.item_id_name,
            timestamp_column="timestamp"
        )

        prediction = self.predictor.predict(past_data)

        return prediction.loc[self.item_id]


if __name__ == '__main__':

    ### preprocess data
    # load data
    data = pd.read_csv(
        r'D:\04_GitRepos\deq_demonstrator\data\01_input\02_electric_loadprofiles_HTW\el_loadprofiles_HTW_processed_0.csv')

    # Define a dictionary to map old column names to new column names by position
    column_rename_dict = {"Unnamed: 0": 'timestamp', "0": 'target'}

    # Use the rename method to rename columns
    data.rename(columns=column_rename_dict, inplace=True)

    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=False)
    data["timestamp"] = data["timestamp"].dt.tz_localize(None)

    max_datetime = pd.to_datetime('2018-01-23 15:00:00', utc=False)

    # Split the DataFrame based on the threshold
    train_data_df = data[data['timestamp'] <= max_datetime]
    test_data_df = data[data['timestamp'] > max_datetime]

    ### actually use the forecaster class
    pred_1 = AutoGluonForecaster()
    pred_1.train_model(train_data_df, 48)
    forecast = pred_1.predict_model(train_data_df)

    ### some plotting for visualization
    import matplotlib.pyplot as plt

    plt.figure(figsize=(20, 3))

    y_past = train_data_df.loc["target"]
    y_pred = forecast
    y_test = test_data_df.loc["target"][:48]

    plt.plot(y_past[-200:], label="Past time series values")
    plt.plot(y_pred["mean"], label="Mean forecast")
    plt.plot(y_test, label="Future time series values")

    plt.fill_between(
        y_pred.index, y_pred["0.1"], y_pred["0.9"], color="red", alpha=0.1, label=f"10%-90% confidence interval"
    )
    plt.legend()

    plt.show()