import pylsl
from pylsl import StreamInlet
import time
import pandas as pd

file_name_1 = "10_emg_data_1_6.csv"
file_name_2 = "10_emg_data_2_6.csv"

# Resolve the stream by its name
streams = pylsl.resolve_streams()
inlet1 = pylsl.StreamInlet(streams[0])
inlet2 = pylsl.StreamInlet(streams[1])
start_time = time.time()


emg_data1 = []
emg_data2 = []
# Receive and print incoming data
while True:
    sample1, timestamp1 = inlet1.pull_sample()
    print(f"Received1: {sample1} at timestamp {timestamp1}")
    emg_data1.append(sample1)
    sample2, timestamp2 = inlet2.pull_sample()
    print(f"Received2: {sample2} at timestamp {timestamp2}")
    emg_data2.append(sample2)

    if (time.time() - start_time > 10):
            myo_cols = ["Channel_1", "Channel_2", "Channel_3", "Channel_4", "Channel_5", "Channel_6", "Channel_7", "Channel_8"]
            myo_df = pd.DataFrame(emg_data1, columns=myo_cols)
            myo_df.to_csv(file_name_1, index=False)
            myo_df_2 = pd.DataFrame(emg_data2, columns=myo_cols)
            myo_df_2.to_csv(file_name_2, index=False)
            print("CSV Saved at: ", file_name_1)
            print("CSV Saved at: ", file_name_2)
            break