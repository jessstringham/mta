# Importing Libraries
import serial
import time

from main import *

train_order = load_json("config/stop_order.json")
train_order = [tuple(t) for t in train_order]

port = load_text("config/port.txt")

arduino = serial.Serial(port=port, baudrate=9600, timeout=.1)

def write_read(x):
    arduino.write(bytes(x, 'utf-8'))
    time.sleep(0.05)
    return arduino.readline()


def update_lights(train_situation):

    write_read("S")  # reset
    for stop_line in train_order:
        status = train_situation[stop_line]
        print(status)
        write_read(status.color.color)



if __name__ == "__main__":
    c = ConfiguredTransitRequester(
        TrainConfig(
            stops=load_json("config/stops.json"),
            trains=load_json("config/trains.json"),
            combine_similar_trains=load_json("config/combine_similar.json")
        ),
        Requester(key=load_text("config/key")),
        StopColors(stop_config)
    )

    while True:
        r = c.get_status()
        r = {
            k.stop_line: k
            for k in r
        }

        update_lights(r)

        # wait a minute before checking again
        time.sleep(60)
