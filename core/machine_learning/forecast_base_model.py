from abc import ABC, abstractmethod

import pandas as pd


class ForecastBaseModel(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def train_model(self,
                    training_data: pd.DataFrame,
                    target_variable: str,
                    prediction_horizon:int):
        """

        Args:
            training_data (pd.DataFrame):
                "time_id" column contains continous int
                "timestamp" column containing utc timestamp without tz_info
                "target" column contains target values
                index unused
            target_variable(str): Name of target variable in the df
            prediction_horizon (int): number of time steps to be predicted per prediction

        Returns:
            predictor
        """
        pass

    @abstractmethod
    def predict_model(self, past_data:pd.DataFrame):
        """
        Args:
            past_data (pd.DataFrame): such as training_data

        Returns:
            prediction
        """
        pass