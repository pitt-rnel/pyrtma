from dash_extensions.enrich import (
    DashProxy,
    html,
    dcc,
    Input,
    Output,
    State,
    NoOutputTransform,
    callback_context,
)
from dash_extensions import WebSocket
import pyrtma, ctypes, threading, time, sys

# Choose a unique message type id number
MT_SINE_STOP = 9001
MT_SINE_START = 9002

# instantiate client globally
mod = pyrtma.Client()


def send_rtma_signal(MT: int):
    try:
        if not mod.connected:
            mod.connect()
        mod.send_signal(MT)
    except:
        print("Error sending rtma signal")


# Create example app.
app = DashProxy(
    __name__,
    transforms=[NoOutputTransform()],
    title="rtma Dash Websocket Example",
    external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"],
)

init_array = [float("nan")] * 100
app.layout = html.Div(
    [
        html.H1("Dash Websocket Example"),
        WebSocket(id="ws", url="ws://127.0.0.1:5678/"),
        dcc.Store(id="figure-store", data=[{"time": init_array, "value": init_array}]),
        html.Div(
            dcc.Graph(
                id="graph",
                figure={
                    "data": [{"x": init_array, "y": init_array, "type": "scatter"}]
                },
            )
        ),
        html.Div(
            [
                html.Button(
                    "Start", id="start-button", n_clicks=0, className="button-primary"
                ),
                html.Button(
                    "Pause", id="pause-button", n_clicks=0, className="button-primary"
                ),
            ]
        ),
        html.Div(
            [
                html.Br(),
                html.P(
                    [
                        "Use with ",
                        html.Code("example_ws_server.py"),
                        " and ",
                        html.Code("example_sinewave.py --pub"),
                        ".",
                        html.Br(),
                        "Refresh this page after starting ",
                        html.Code("example_ws_server.py"),
                        ".",
                    ]
                ),
            ]
        ),
    ]
)

# Client-side function (for performance) that updates the graph.
update_store = """function(msg, store) {
    if(msg && store){
        const data = JSON.parse(msg.data);  // read the data
        store[0]["time"] = store[0]["time"].slice(1).concat(data.time) // append data (FIFO)
        store[0]["value"] = store[0]["value"].slice(1).concat(data.value)
    }
    return store};  // update store
"""

update_graph = """function(store) {
    if(!store){return {};} // no data just return
    return {data: [{x: store[0]["time"], y: store[0]["value"], type: "scatter"}]}};  // plot the data
"""

app.clientside_callback(
    update_store,
    Output("figure-store", "data"),
    Input("ws", "message"),
    State("figure-store", "data"),
)
app.clientside_callback(
    update_graph, Output("graph", "figure"), Input("figure-store", "data")
)


@app.callback(Input("start-button", "n_clicks"), Input("pause-button", "n_clicks"))
def start_callback(start, pause):
    button_clicked = callback_context.triggered_id
    if button_clicked == "start-button" and start:
        send_rtma_signal(MT_SINE_START)
    elif button_clicked == "pause-button" and pause:
        send_rtma_signal(MT_SINE_STOP)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port="8050",
        debug=True,
        use_reloader=False,  # prevents code from running twice, but editing this script will not hot-reload
    )
