import numpy as np
from pylsl import StreamInlet, resolve_stream, StreamOutlet, StreamInfo
import scipy
from scipy.signal import butter, lfilter
import csv
import time
import warnings
import matplotlib.pyplot as plt


emg_ch = 7  # 34:APL-R, 35:APL-L, 36:ED-R, 37:ED-L, 38:FD-R, 39:FD-L
emg_ch_right = 4
emg_ch_left = 4

fs = 200
win_len = 1
filt_low = 4
filt_high = 10
filt_order = 1




def start_lsl_stream():
    """
    Starts listening to EEG lsl stream. Will get "stuck" if no stream is found.
    :param type: string - type of stream type (e.g. 'EEG' or 'marker')
    :return: lsl_inlet; pysls.StreamInlet object
    """

    streams = resolve_stream()
    #changed from old code which gad as arguments type and 'type'
    '''
    if len(streams) > 1:
        warnings.warn('Number of EEG streams is > 0, picking the first one.')
    lsl_inlet = StreamInlet(streams[0])
    lsl_inlet.pull_sample()  # need to pull first sample to get buffer started for some reason
    print("Stream started.")
    '''
    inlet1 = StreamInlet(streams[0])
    inlet2 = StreamInlet(streams[1])
    return inlet1, inlet2

def butter_bandpass(lowcut, highcut, fs, order):
    b, a = butter(order, [lowcut, highcut], fs=fs, btype='band', output="ba")
    return b, a

def pull_from_buffer(lsl_inlet, max_tries=10):
    """
    Pull data from the provided lsl inlet and return it as an array.
    :param lsl_inlet: lsl inlet object
    :param max_tries: int; number of empty chunks after which an error is thrown.
    :return: np.ndarray of shape (n_samples, n_channels)
    """
    # Makes it possible to run experiment without eeg data for testing by setting lsl_inlet to None
    

    pull_at_once = 200
    samps_pulled = 200
    n_tries = 0

    samples = []
    while pull_at_once == samps_pulled:
        data_lsl, _ = lsl_inlet.pull_chunk(max_samples=pull_at_once)
        arr = np.array(data_lsl)
        if len(arr) > 0:
            samples.append(arr)
            samps_pulled = len(arr)
        else:
            n_tries += 1
            time.sleep(0.7)
            if n_tries == max_tries:
                raise ValueError("Stream does not seem to provide any data.")
    #print('samples',samples)
    return np.vstack(samples)

def pull_data(lsl_inlet, data_lsl, replace=True):
    new_data = pull_from_buffer(lsl_inlet)
    if replace or data_lsl is None:
        data_lsl = new_data
    else:
        data_lsl = np.vstack([data_lsl, new_data])
    return data_lsl



def get_emg(lsl_inlet, data_lsl, emg_ch, win_len):
    # print(np.shape(data_lsl))
    data_lsl = pull_data(lsl_inlet=lsl_inlet, data_lsl=data_lsl, replace=False)    
    #print('lsl_inlet',lsl_inlet.info())
    emg = data_lsl[:, emg_ch] # select emg channel
    #print('emg',len(emg))
    #print('data_lsl',len(data_lsl))
    win_samp = win_len * fs # define win len (depending on fs)
    #print('win_samp',win_samp)
    emg_chunk = 0
    if len(emg) > win_samp:   # wait until data win is long enough
        emg_win = emg[-win_samp:-1] # pull data from time point 0 to -win_size
        emg_filt = lfilter(b, a, emg_win) # applying the filter (no need to change)
        emg_env = np.abs(scipy.signal.hilbert(emg_filt)) # calculating envelope
        # emg_smooth = scipy.signal.savgol_filter(emg_env, window_length=300, polyorder=3) # optional: smooth the signal (avoid data jumps)
        '''
        # for testing
        plt.plot(emg_filt,label='bp_filt')
        plt.plot(emg_env,label='envelope')
        #plt.plot(emg_smooth,label='smooth')
        plt.grid()
        plt.legend()
        plt.show()
        '''
        
        chunk_size = 4 # start: 20 # change to 4 eventually later - 200HZ sampling rate
        emg_chunk = np.mean(np.power(emg_env[-chunk_size:-1], 2))
        # offset = 100
        # emg_chunk = emg_chunk - offset
        # if emg_chunk < 0: emg_chunk = 0
        print('emg_chunk',emg_chunk)
    return emg_chunk, data_lsl



# =======================================================================================================================
# Start up
inlet1, inlet2 = start_lsl_stream()
data_lsl = None
b, a = butter_bandpass(filt_low, filt_high, fs, filt_order)

# =======================================================================================================================


start_time = time.time()



while True:
   
    if (time.time() - start_time > 5):
        force_right = 0
        force_left = 0
        force_right, data_lsl = get_emg(lsl_inlet=inlet1, data_lsl=data_lsl, emg_ch=emg_ch_right,
                                                        win_len=win_len)
        force_left, data_lsl = get_emg(lsl_inlet=inlet2, data_lsl=data_lsl, emg_ch=emg_ch_left,
                                                        win_len=win_len)


        print('Left: ' + str(int(force_left)) + '     Right: ' + str(int(force_right)))
