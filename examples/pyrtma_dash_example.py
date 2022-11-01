from dash import Dash, dcc, html, Input, Output, State
import pyrtma, ctypes, threading, time, sys
from queue import Queue


# Choose a unique message type id number
MT_USER_MESSAGE = 1234

# Create a user defined message from a ctypes.Structure or basic ctypes
@pyrtma.msg_def
class USER_MESSAGE(pyrtma.MessageData):
    _fields_ = [
        ("str", ctypes.c_byte * 64),
        ("val", ctypes.c_double),
        ("arr", ctypes.c_int * 8),
    ]

    type_id: int = MT_USER_MESSAGE
    type_name: str = "USER_MESSAGE"


# instantiate client globally
mod = pyrtma.Client()

app = Dash(
    __name__,
    title="RTMA Example",
    external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"],
)

msg_queue = Queue()  # global message queue


def send_rtma_message(msg):
    try:
        if not mod.connected:
            mod.connect()
        mod.send_message(msg)
    except:
        print("Error sending RTMA message")


class RtmaThread(threading.Thread):
    def __init__(self):
        self.running = False
        self.connected = mod.connected
        super().__init__()
        self.setDaemon(True)
        pass

    def run(self):
        self.running = True

        connect_attempts = 0
        max_attempts = 10
        while self.running:
            # connect to RTMA
            if not (mod.connected and self.connected):
                connect_attempts += 1
                try:
                    mod.connect()
                    self.connected = mod.connected
                    connect_attempts = 0
                    print("Connected to RTMA message manager")
                except:
                    if connect_attempts < max_attempts:
                        print(
                            "Warning: Exception connecting to message manager in RtmaThread, trying again."
                        )
                        time.sleep(2)
                        continue
                    else:
                        print(
                            "ERROR: Could not connect to message manager in RtmaThread, exceeded max tries.",
                            file=sys.stderr,
                        )
                        self.running = False
                        break

            # subscribe to message
            if mod.connected and self.connected:
                print("Subscribing to USER_MESSAGE")
                try:
                    mod.subscribe([MT_USER_MESSAGE])
                except:
                    self.connected = False
                    print("Warning: Exception when subscribing to USER_MESSAGE")
                    time.sleep(2)

            # read messages
            while self.running and mod.connected and self.connected:
                try:
                    msg = mod.read_message(timeout=0.200)

                    if msg is not None and msg.name == "USER_MESSAGE":
                        msg_queue.put(msg)
                except:
                    self.connected = False
                    print("Exception in RtmaThread read loop")
                    time.sleep(2)


send_txt_style = {"width": "100%", "height": "85px", "resize": "none", "margin": "auto"}

read_txt_style = {"width": "100%", "height": "400px", "margin": "auto"}

div_style = {"width": "90%", "margin": "auto"}

app.layout = html.Div(
    [
        html.H2("LabSwitchboard Dash Example"),
        html.Div(
            html.Button(
                "Send Message", id="send-msg", n_clicks=0, className="button-primary"
            ),
            style=div_style,
        ),
        html.Div(
            [
                html.H4("Sent Message:"),
                dcc.Textarea(
                    id="send-txt",
                    value="",
                    disabled=True,
                    readOnly=True,
                    style=send_txt_style,
                ),
            ],
            style=div_style,
        ),
        html.Div(
            [
                html.H4("Received messages:"),
                dcc.Textarea(
                    id="read-txt",
                    value="",
                    disabled=True,
                    readOnly=True,
                    style=read_txt_style,
                ),
            ],
            style=div_style,
        ),
        dcc.Interval(
            id="interval-component", interval=500, n_intervals=0
        ),  # interval in ms
    ]
)


@app.callback(Output("send-txt", "value"), Input("send-msg", "n_clicks"))
def send_callback(n_clicks):
    if n_clicks:
        # Build a packet to send and send it
        msg = USER_MESSAGE()
        py_string = b"Hello World"
        msg.str[: len(py_string)] = py_string
        msg.val = n_clicks + 0.123
        msg.arr[:] = list(range(8))
        send_rtma_message(msg)
        out = str(msg)
    else:
        out = ""
    return out


@app.callback(
    Output("read-txt", component_property="value"),
    State("read-txt", component_property="value"),
    Input("interval-component", "n_intervals"),
)
def interval_callback(txt, n):
    MAX_ROWS = 50
    while not msg_queue.empty():
        msg = msg_queue.get().data
        txt = str(msg) + "\n" + txt
        if len(txt.splitlines()) > MAX_ROWS:
            txt = "\n".join(txt.split("\n")[:MAX_ROWS])
    return txt


if __name__ == "__main__":
    try:
        rtma_thread = RtmaThread()
        rtma_thread.start()
        app.run(
            host="127.0.0.1",
            port="8050",
            debug=True,
            use_reloader=False,  # prevents code from running twice, but editing this script will not hot-reload
        )
    finally:
        mod.disconnect()
