import time
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
import pandas as pd

file_name_1 = "10_emg_data_1.csv"
file_name_2 = "10_emg_data_2.csv"

# Create stream info for the first EMG stream
info_emg1 = StreamInfo('EMG_Stream1', 'EMG', 1, 1000, 'float32', 'EMG1_ID')

# Create a stream outlet for the first EMG stream
outlet_emg1 = StreamOutlet(info_emg1)

# Create stream info for the second EMG stream
info_emg2 = StreamInfo('EMG_Stream2', 'EMG', 1, 1000, 'float32', 'EMG2_ID')

# Create a stream outlet for the second EMG stream
outlet_emg2 = StreamOutlet(info_emg2)

# Send EMG data
for i in range(10):
    emg_data1 = [0.1 * i]  # Replace this with your actual EMG data for stream 1
    emg_data2 = [0.2 * i]  # Replace this with your actual EMG data for stream 2

    outlet_emg1.push_sample(emg_data1)
    outlet_emg2.push_sample(emg_data2)

    time.sleep(1)

# Resolve the streams
streams_emg1 = resolve_stream('type', 'EMG', timeout=5)
streams_emg2 = resolve_stream('type', 'EMG', timeout=5)

# Create inlets for receiving data
inlet_emg1 = None
inlet_emg2 = None

if streams_emg1:
    inlet_emg1 = StreamInlet(streams_emg1[0])

if streams_emg2:
    inlet_emg2 = StreamInlet(streams_emg2[0])

# Receive EMG data
print('Waiting for EMG data...')
start_time = time.time()
while True:
    sample_emg1, timestamp_emg1 = inlet_emg1.pull_sample()
    sample_emg2, timestamp_emg2 = inlet_emg2.pull_sample()

    if sample_emg1:
        print(f'Received EMG data from Stream 1: {sample_emg1}')

    if sample_emg2:
        print(f'Received EMG data from Stream 2: {sample_emg2}')

    