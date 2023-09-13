import unittest
import random
import threading
import time
import logging

import pyrtma
from .test_msg_defs.test_defs import *

from pyrtma.client import Client
from pyrtma.message import *
import pyrtma.manager
from pyrtma.manager import MessageManager


class TestSync(unittest.TestCase):
    """Test sending messages through MessageManager."""

    def setUp(self):
        self.port = random.randint(1000, 10000)  # random port
        self.addr = f"127.0.0.1:{self.port}"

        pyrtma.manager.LOG_LEVEL = logging.ERROR
        self.manager = MessageManager(
            ip_address="127.0.0.1",
            port=self.port,
            timecode=False,
            debug=False,
            send_msg_timing=True,
        )
        self.manager_thread = threading.Thread(
            target=self.manager.run,
        )
        self.manager_thread.start()
        time.sleep(0.250)

    def tearDown(self):
        self.manager.close()
        self.manager_thread.join()
        for mod in self.manager.modules:
            mod.close()

    def test_version_mismatch(self):
        publisher = Client()
        publisher.connect(self.addr)
        subscriber = Client()
        subscriber.connect(self.addr)
        time.sleep(0.250)

        subscriber.subscribe([MT_SET_START])
        subscriber.wait_for_acknowledgement()

        header = MessageHeader()
        header.msg_type = MT_SET_START
        header.msg_count = 1
        header.send_time = time.perf_counter()
        header.num_data_bytes = 0

        # Change the version to create a mismatch between sender and receiver
        header.version = 0xDEADBEEF

        publisher.forward_message(header, MDF_SET_START())

        with self.assertRaises(pyrtma.message.InvalidMessageDefinition):
            msg = subscriber.read_message(timeout=0.100, sync_check=True)

    def test_size_mismatch(self):
        publisher = Client()
        publisher.connect(self.addr)
        subscriber = Client()
        subscriber.connect(self.addr)
        time.sleep(0.250)

        subscriber.subscribe([MT_SET_START])
        subscriber.wait_for_acknowledgement()

        header = MessageHeader()
        header.msg_type = MT_SET_START
        header.msg_count = 1
        header.send_time = time.perf_counter()

        # Create a size mismatch between sender and receiver
        data = MDF_TRIAL_METADATA()
        header.num_data_bytes = data.size

        publisher.forward_message(header, data)

        with self.assertRaises(pyrtma.message.InvalidMessageDefinition):
            msg = subscriber.read_message(timeout=0.100, sync_check=True)
