import pandas as pd
from config.definitions import ROOT_DIR

import lightning.pytorch as pl
from lightning.pytorch.callbacks import EarlyStopping, LearningRateMonitor
from lightning.pytorch.tuner import Tuner
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_forecasting import NHiTS



# load data
data = pd.read_csv(
    r'D:\04_GitRepos\deq_demonstrator\data\01_input\02_electric_loadprofiles_HTW\el_loadprofiles_HTW_processed_0.csv',
    index_col=0, parse_dates=True)

data["time_idx"] = range(len(data))
data["case"] = 0

# Define your target and dynamic features
target_col = '0'
time_idx_col = 'time_idx'
max_prediction_length = 1  # Adjust as needed
max_encoder_length = 3  # Adjust as needed

# Create a TimeSeriesDataSet
dataset = TimeSeriesDataSet(
    data,
    time_idx=time_idx_col,
    target=target_col,
    group_ids="case",
    time_varying_unknown_reals=[target_col],  # List of time-varying unknown real variables
    min_prediction_length=1,
    max_prediction_length=max_prediction_length,
    min_encoder_length=max_encoder_length//2,
    max_encoder_length=max_encoder_length,
)

# Optionally, you can create dataloaders for training and validation
train_dataloader = dataset.to_dataloader(train=True, batch_size=64)
val_dataloader = dataset.to_dataloader(train=False, batch_size=64)


# define dataset
max_encoder_length = 36
max_prediction_length = 6
training_cutoff = pd.Timestamp("2018-01-02 00:00:00+00:00", tz="UTC")  # day for cutoff


training = TimeSeriesDataSet(
    data[lambda x: x.index < training_cutoff],  # Subset of your data for training
    time_idx="time_idx",
    target="0",
    max_encoder_length=max_encoder_length,
    max_prediction_length=max_prediction_length,
    group_ids=["0"],
)

# create validation and training dataset
validation = TimeSeriesDataSet.from_dataset(training, data,
                                            min_prediction_idx=training.index.time.max() + 1,
                                            stop_randomization=True)
batch_size = 128
train_dataloader = training.to_dataloader(train=True, batch_size=batch_size, num_workers=2)
val_dataloader = validation.to_dataloader(train=False, batch_size=batch_size, num_workers=2)

# define trainer with early stopping
early_stop_callback = EarlyStopping(monitor="val_loss", min_delta=1e-4, patience=1, verbose=False, mode="min")
lr_logger = LearningRateMonitor()
trainer = pl.Trainer(
    max_epochs=100,
    accelerator="auto",
    gradient_clip_val=0.1,
    limit_train_batches=30,
    callbacks=[lr_logger, early_stop_callback],
)

# create the model
tft = TemporalFusionTransformer.from_dataset(
    training,
    learning_rate=0.03,
    hidden_size=32,
    attention_head_size=1,
    dropout=0.1,
    hidden_continuous_size=16,
    output_size=7,
    loss=QuantileLoss(),
    log_interval=2,
    reduce_on_plateau_patience=4
)
print(f"Number of parameters in network: {tft.size()/1e3:.1f}k")

# find optimal learning rate (set limit_train_batches to 1.0 and log_interval = -1)
res = Tuner(trainer).lr_find(
    tft, train_dataloaders=train_dataloader, val_dataloaders=val_dataloader, early_stop_threshold=1000.0, max_lr=0.3,
)

print(f"suggested learning rate: {res.suggestion()}")
fig = res.plot(show=True, suggest=True)
fig.show()

# fit the model
trainer.fit(
    tft, train_dataloaders=train_dataloader, val_dataloaders=val_dataloader,
)

