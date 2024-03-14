
from pylsl import StreamInfo, StreamOutlet
import time

# Create a stream info with the name 'MyStream', one channel, and float data
info = StreamInfo('MyStream', 'Markers', 1, 0, 'float32', 'myuid34234')

# Create a stream outlet
outlet = StreamOutlet(info)

# Send some data
for i in range(10):
    sample = [i]  # A single floating-point value as an example
    outlet.push_sample(sample)
    time.sleep(1)  # Sleep for 1 second between samples

