import multiprocessing
from pythonosc import udp_client
import struct
import math
from quick_queue import QQueue


class DataHandler:
    """
    EMG/IMU/Classifier data handler.
    """

    def __init__(self, config):
        self.osc = udp_client.SimpleUDPClient(config.OSC_ADDRESS, config.OSC_PORT)
        self.printEmg = config.PRINT_EMG
        self.printImu = config.PRINT_IMU
        self.myo_imu_data = multiprocessing.Queue()
        # self.p = multiprocessing.Process(target=self.process, args=(self.myo_data0, self.myo_data1))
        # self.p.start()

    def process(q1, q2):
        return q1.get(), q2.get()

    def handle_emg(self, payload):
        """
        Handle EMG data.
        :param payload: emg data as two samples in a single pack.
        """
        myo_data0 = []
        myo_data1 = []
        if self.printEmg:
            print("EMG", payload['connection'], payload['atthandle'], payload['value'])

        # Send both samples
        self._send_single_emg(payload['connection'], payload['value'][0:8])
        self._send_single_emg(payload['connection'], payload['value'][8:16])

    # print(payload['atthandle'])

    def _send_single_emg(self, conn, data):
        '''
        #print("conn: {}, data {}".format(conn, data_new))

        data_new = []
        builder = udp_client.OscMessageBuilder("/myo/emg")
        builder.add_arg(str(conn), 's')
        for i in struct.unpack('<8b ', data):
            builder.add_arg(i / 127, 'f')  # Normalize
            data_new.append(i)
        if conn == 0:
            self.myo_data0.put_nowait(data_new)
        if conn == 1:
            self.myo_data1.put_nowait(data_new)
            print(data_new)

        self.osc.send(builder.build())
        '''

        # print("conn: {}, data {}".format(conn, data_new))

        data_new = []
        builder = udp_client.OscMessageBuilder("/myo/emg")
        builder.add_arg(str(conn), 's')
        for i in struct.unpack('<8b ', data):
            builder.add_arg(i / 127, 'f')  # Normalize
            data_new.append(i)
        '''
        new_dict = {'emg': {str(conn): data_new}}
        print({str(conn): data_new})
        self.myo_imu_data.put(new_dict)
        '''
        if conn == 0:
            # print("0", data_new)
            dict0 = {'emg': {str(conn): data_new}}
            self.myo_imu_data.put(dict0)
        if conn == 1:
            # self.myo_data1.put(data_new)
            # print("1", data_new)
            dict1 = {'emg': {str(conn): data_new}}
            self.myo_imu_data.put(dict1)
        self.osc.send(builder.build())

    def handle_imu(self, payload):
        """
        Handle IMU data.
        :param payload: imu data in a single byte array.
        """
        if self.printImu:
            print("IMU", payload['connection'], payload['atthandle'], payload['value'])
        # Send orientation
        conn = payload['connection']
        data = payload['value'][0:8]
        builder = udp_client.OscMessageBuilder("/myo/orientation")
        builder.add_arg(str(payload['connection']), 's')
        roll, pitch, yaw = self._euler_angle(*(struct.unpack('hhhh', data)))
        # Normalize to [-1, 1]
        builder.add_arg(roll / math.pi, 'f')
        builder.add_arg(pitch / math.pi, 'f')
        builder.add_arg(yaw / math.pi, 'f')
        self.osc.send(builder.build())

        # Send accelerometer
        data = payload['value'][8:14]
        builder = udp_client.OscMessageBuilder("/myo/accel")
        builder.add_arg(str(payload['connection']), 's')
        accelerometer = self._vector_magnitude(*(struct.unpack('hhh', data)))
        builder.add_arg(accelerometer, 'f')
        self.osc.send(builder.build())

        # Send gyroscope
        data = payload['value'][14:20]
        builder = udp_client.OscMessageBuilder("/myo/gyro")
        builder.add_arg(str(payload['connection']), 's')
        gyro = self._vector_magnitude(*(struct.unpack('hhh', data)))
        builder.add_arg(gyro, 'f')
        self.osc.send(builder.build())

        new_dict = {'imu': {str(conn): [ roll / math.pi, pitch / math.pi,  yaw/math.pi, accelerometer,  gyro ]} }
        #print(new_dict)
        self.myo_imu_data.put(new_dict)

    @staticmethod
    def _euler_angle(w, x, y, z):
        """
        From https://en.wikipedia.org/wiki/Conversion_between_quaternions_and_Euler_angles.
        """
        # roll (x-axis rotation)
        sinr_cosp = +2.0 * (w * x + y * z)
        cosr_cosp = +1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # pitch (y-axis rotation)
        sinp = +2.0 * (w * y - z * x)
        if math.fabs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # use 90 degrees if out of range
        else:
            pitch = math.asin(sinp)

        # yaw (z-axis rotation)
        siny_cosp = +2.0 * (w * z + x * y)
        cosy_cosp = +1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    @staticmethod
    def _vector_magnitude(x, y, z):
        return math.sqrt(x * x + y * y + z * z)
