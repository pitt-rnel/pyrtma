import ctypes
import random
import threading
import time
import unittest

from pyrtma import msg_def
from pyrtma.client import Client
from pyrtma.manager import MessageManager

# Choose a unique message type id number
MT_TEST_MESSAGE = 1234
MT_TEST_MESSAGE2 = 5678


@msg_def
class TEST_MESSAGE(ctypes.Structure):
    _fields_ = [
        ("str", ctypes.c_byte * 64),
        ("val", ctypes.c_double),
        ("arr", ctypes.c_int * 8),
    ]

    type_id: int = MT_TEST_MESSAGE
    type_name: str = "TEST_MESSAGE"


@msg_def
class TEST_MESSAGE2(ctypes.Structure):
    _fields_ = [
        ("val", ctypes.c_double),
    ]

    type_id: int = MT_TEST_MESSAGE2
    type_name: str = "TEST_MESSAGE2"


def wait_for_message():
    """
    Helper function for allowing time for a message to reach the manager.
    """
    time.sleep(0.1)


class TestSingleClient(unittest.TestCase):
    """
    Test interactions between a single client and manager.
    """

    def setUp(self):
        self.port = random.randint(1000, 10000)  # random port
        self.module_id = 11
        self.client = Client(module_id=self.module_id, host_id=0, timecode=False)

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
        wait_for_message()

    def tearDown(self):
        self.manager.close()
        self.manager_thread.join()
        for mod in self.manager.modules:
            mod.close()

    def test_whenClientConnects_clientConnectsToMessageManager(self):
        """
        Test if client module is connected when connect is called.
        """
        # Arrange

        # Act
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()

        # Assert
        self.assertTrue(self.client.connected, msg="Client not connected.")
        self.assertIn(
            self.module_id,
            [mod.id for mod in self.manager.modules.values()],
            msg="Module id not found in Messager Manager modules.",
        )

    def test_whenClientSubscribes_clientIsSubscribedToMessageType(self):
        """
        Test if client is subscribed to message type when subscribe is called.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()

        # Act
        self.client.subscribe(MT_TEST_MESSAGE)
        wait_for_message()

        # Assert
        self.assertIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id not found in TEST_MESSAGE subscriptions.",
        )

    def test_whenClientSubscribesMulti_clientIsSubscribedToMessageTypes(self):
        """
        Test if client is subscribed to message types when multiple message
            types are sent to subscribe.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()

        # Act
        self.client.subscribe([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()

        # Assert
        self.assertIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id not found in TEST_MESSAGE subscriptions",
        )
        self.assertIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE2]],
            msg="Module id not found in TEST_MESSAGE2 subscriptions",
        )

    def test_whenClientUnsubscribes_clientIsUnsubscribedFromMessageType(self):
        """
        Test if client is unsubscribed from message type when unsubscribe is called.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()
        self.client.subscribe(MT_TEST_MESSAGE)
        wait_for_message()

        # Act
        self.client.unsubscribe(MT_TEST_MESSAGE)
        wait_for_message()

        # Assert
        self.assertNotIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id found in TEST_MESSAGE subscriptions.",
        )

    def test_whenClientUnsubscribesMulti_clientIsUnsubscribedFromMessageTypes(self):
        """
        Test if client is unsubscribed from message types when multiple message
            types are sent to unsubscribe.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()
        self.client.subscribe([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()

        # Act
        self.client.unsubscribe([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()

        # Assert
        self.assertNotIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id found in TEST_MESSAGE subscriptions.",
        )
        self.assertNotIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE2]],
            msg="Module id found in MT_TEST_MESSAGE2 subscriptions.",
        )

    def test_whenClientPauses_clientIsRemovedFromMessageType(self):
        """
        Test if client is unsubscribed from message type when pause is called.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()
        self.client.subscribe(MT_TEST_MESSAGE)
        wait_for_message()

        # Act
        self.client.pause_subscription(MT_TEST_MESSAGE)
        wait_for_message()

        # Assert
        self.assertNotIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id found in TEST_MESSAGE subscriptions.",
        )

    def test_whenClientPausesMulti_clientIsRemovedFromMessageTypes(self):
        """
        Test if client is unsubscribed from message types when multiple message
            types are sent to pause.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()
        self.client.subscribe([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()

        # Act
        self.client.pause_subscription([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()

        # Assert
        self.assertNotIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id found in TEST_MESSAGE subscriptions.",
        )
        self.assertNotIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE2]],
            msg="Module id found in MT_TEST_MESSAGE2 subscriptions.",
        )

    def test_whenClientResumes_clientIsAddedToMessageType(self):
        """
        Test if client is subscribed to message type when resume is called.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()
        self.client.subscribe(MT_TEST_MESSAGE)
        wait_for_message()
        self.client.pause_subscription(MT_TEST_MESSAGE)
        wait_for_message()

        # Act
        self.client.resume_subscription(MT_TEST_MESSAGE)
        wait_for_message()

        # Assert
        self.assertIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id not found in TEST_MESSAGE subscriptions",
        )

    def test_whenClientResumesMulti_clientIsAddedToMessageType(self):
        """
        Test if client is subscribed to message types when multiple message
            types are sent to resume.
        """
        # Arrange
        self.client.connect(server_name=f"127.0.0.1:{self.port}")
        wait_for_message()
        self.client.subscribe([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()
        self.client.pause_subscription([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()

        # Act
        self.client.resume_subscription([MT_TEST_MESSAGE, MT_TEST_MESSAGE2])
        wait_for_message()

        # Assert
        self.assertIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE]],
            msg="Module id not found in TEST_MESSAGE subscriptions",
        )
        self.assertIn(
            self.module_id,
            [mod.id for mod in self.manager.subscriptions[MT_TEST_MESSAGE2]],
            msg="Module id not found in TEST_MESSAGE2 subscriptions",
        )
