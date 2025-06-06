from .public.myohw import *
import struct
import pyomyo


class Myo():
    """
    Wrapper for a Myo, its name, address, firmware and most importantly, connection id.
    """

    def __init__(self, address):
        self.address = address  ### MAC-address in reversed byte format; e.g.: b'\xc6z\xd95\x07\xec'

        ###  convert each byte of the address to its hexadecimal representation.
        ### The '02x' format specifier ensures that each hexadecimal representation is zero-padded to have at least two characters:
        hex_list = [format(byte, '02x') for byte in address]
        ### join the double-characters with hyphens '-' in reverse order [::-1]
        self.mac_address = '-'.join(hex_list[::-1])  ### MAC-address in usual format, e.g.: ec-07-35-d9-7a-c6

        self.connection_id = None
        self.device_name = None
        self.firmware_version = None
        self.battery_level = None
        self.connected = False
        self.emg_handlers = []

    def add_emg_handler(self, h):
        self.emg_handlers.append(h)

    def set_id(self, connection_id):
        """
        Set connection id, required for every write/read attribute message.
        """
        self.connection_id = connection_id
        return self

    def set_connected(self, connected):
        self.connected = connected

    def handle_attribute_value(self, payload):
        """
        When attribute values are not EMG/IMU related, are a Myo attribute being read.
        """
        if self.connection_id == payload['connection']:
            if payload['atthandle'] == ServiceHandles.DeviceName:
                self.device_name = payload['value'].decode()
                # print("Device name", payload['value'].decode())
            elif payload['atthandle'] == ServiceHandles.FirmwareVersionCharacteristic:
                self.firmware_version = payload['value']
                # print("Firmware version", payload['value'])
                if not payload['value'] == b'\x01\x00\x05\x00\xb2\x07\x02\x00':
                    print("MYO WITH UNEXPECTED FIRMWARE, MAY NOT BEHAVE PROPERLY.", payload['value'])
            elif payload['atthandle'] == ServiceHandles.BatteryCharacteristic:
                self.battery_level = payload['value']
            else:
                print("UNEXPECTED ATTRIBUTE VALUE: ", payload)

    def ready(self):
        """
        :return:True if every field is valid, False otherwise.
        """
        return self.address is not None and \
            self.connection_id is not None and \
            self.device_name is not None and \
            self.firmware_version is not None and \
            self.battery_level is not None

    def __str__(self):
        return "Myo: " + str(self.device_name) + ", " + \
            "Battery level: " + str(*struct.unpack('b', self.battery_level)) + "/100, " + \
            "Connection: " + str(self.connection_id) + ", " + \
            "Address: " + str(self.address) + ", " + \
            "Firmware: " + str(self.firmware_version)
