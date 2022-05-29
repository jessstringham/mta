"""Oh it's another script to get nyc train lines that I wrote kinda quick
instead of catching the train. I need to load it onto my raspberry pi, and
my favorite way is using github. It's not very user-friendly right now, but
maybe some snippets are helpful.

Start here: https://new.mta.info/developers

Sign up for an API key and create a file that contains it
    echo "your key!" > config/key

`config/trains.json` should contain a list of stops that you care about.
  name: can be whatever you want to label it
  stop: needs to be the MTA id for the stop and direction. [1]
  distance: how many minutes walk it is.
  trains: list of trains that you want to filter for.

[1] The stops are found after accepting the terms and conditions here
http://web.mta.info/developers/developer-data-terms.html#data
under "New York City Transit Subway", which downloads a folder.
There's a file called stops.txt that maps the stop id to a name you probably
recognize. Assuming you want both directions, you'll want both
e.g. 14 St-Union Sq is 635, but if you care about both directions, grab
both 635N and 635S. I haven't figured out the trick for which is N and which
is S yet, esp for trains that go east/west. I managed by grabbing two stations
next to each other and then pulling the times for trains, and then trying to
reason through it that way.

    [
        {
            "name": "Union Square - BK",
            "stop": "635S",
            "distance": 5,
            "trains": ["4"]
        }
    ]


`config/trains.json` should contain a list of dictionaries with the uri
(from https://api.mta.info/#/subwayRealTimeFeeds) and trains to search for.
The list of trains are a bit of a optimization used to filter down which
stops to search for.

    [
        {
            "url": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
            "trains": ["G"],
        }
    ]

config/combine.json is a hack to combine some trains where I don't want
separate configs for, because they're basically the route for me.

The data is formatted as a "GTFS protobuf", as described on https://api.mta.info/#/HelpDocument.
I compiled both the gtfs and the MTA-specific extension, but didn't end up using the extension.
Use request library's response.content instead of response.text so you get the raw bytes!

"""
import datetime
import json
from collections import namedtuple

import requests

from proto import gtfs_realtime_pb2
import stop_config

def load_json(filename):
    with open(filename) as f:
        r = json.load(f)
    return r

def load_text(filename):
    with open(filename) as f:
        key = f.read().strip()
    return key


# contains some debug info too

NextTrain = namedtuple("NextTrain", ["stop_line", "color", "time", "time_to_walk", "train_times"])


class TrainConfig(namedtuple("TrainConfig", ["stops", "trains", "combine_similar_trains"])):
    def __init__(self, *args, **kwargs):
        super(TrainConfig).__init__(*args)

        # eh, just reformat some of the data
        self.stop_to_name = {
            s["stop"]: s["name"]
            for s in self.stops
        }

        self.stops_to_distance = {
            s["name"]: s["distance"]
            for s in self.stops
        }

        self.stop_lines = set(
            (s["name"], train)
            for s in self.stops
            for train in s['trains']
        )

        self.stop_line_ordered = list(sorted(self.stop_lines))

class Requester(namedtuple("Requester", ["key"])):
    def make_request(self, url):
        r = requests.get(url, headers={"x-api-key": self.key})
        return r

    def parse_result(self, result):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(result)

        result = []
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                for stop in entity.trip_update.stop_time_update:
                    line = entity.trip_update.trip.route_id
                    result.append({
                        "line": line,
                        "stop": stop.stop_id,
                        "time": datetime.datetime.fromtimestamp(stop.arrival.time)
                    })
        return result

    def load_for_train(self, url):
        r = self.make_request(url)
        if r.status_code == 200:
            return self.parse_result(r.content)

class StopColors(namedtuple("StopColors", ["stop_config"])):
    def make_call_about_train(self, time_to_walk, stop_times):
        # clear the time in case there are no trains at all
        best_time = None
        color = None
        for time in sorted(stop_times):  # important to sort here!
            if time < time_to_walk:  # too soon
                continue
            elif time < time_to_walk + self.stop_config.StopConfig.TIMING_GETTING_CLOSE:
                best_time = time
                color = self.stop_config.StopConfig.COLOR_GETTING_CLOSE
                # break  in this case, actually check if there's a better time
            elif time < time_to_walk + self.stop_config.StopConfig.TIMING_HAVE_TIME:
                best_time = time
                color = self.stop_config.StopConfig.COLOR_HAVE_TIME
                break
            elif time < time_to_walk + self.stop_config.StopConfig.TIMING_CAN_WAIT:
                best_time = time
                color = self.stop_config.StopConfig.COLOR_CAN_WAIT
                break
            elif color is None and time < time_to_walk + self.stop_config.StopConfig.TIMING_TOO_FAR:
                best_time = time
                color = self.stop_config.StopConfig.COLOR_TOO_FAR
                break
        color = color or self.stop_config.StopConfig.COLOR_WAY_TOO_FAR
        return best_time, color


class ConfiguredTransitRequester(namedtuple("ConfiguredTransitRequester", ["config", "requester", "stop_colors"])):
    def load_relevant_train_times(self):
        times_per_stop_line = {
            stop_line: []
            for stop_line in self.config.stop_lines
        }
        for url in self.config.trains:
            query_results = self.requester.load_for_train(url)

            # grab the time after we get all the requests back!
            now = datetime.datetime.now()

            # now check for the important stops
            for result in query_results:
                line = self.config.combine_similar_trains.get(result["line"], result["line"])
                if result["stop"] not in self.config.stop_to_name:
                    continue

                stop = self.config.stop_to_name[result['stop']]
                stop_line = (stop, line)
                # not relevant train, so skip it!
                if stop_line not in self.config.stop_lines:
                    continue

                times_per_stop_line[stop_line].append((result['time'] - now).seconds // 60)
        return times_per_stop_line

    def get_status(self):
        times_per_stop_line = self.load_relevant_train_times()

        result = []
        for stop_line in self.config.stop_line_ordered:
            stop, line = stop_line
            times = times_per_stop_line.get(stop_line, [])

            time_to_walk = self.config.stops_to_distance[stop]
            time, color = self.stop_colors.make_call_about_train(time_to_walk, times)

            result.append(NextTrain(stop_line, color, time, time_to_walk, sorted(times)))
        return result


if __name__ == '__main__':
    c = ConfiguredTransitRequester(
        TrainConfig(
            stops=load_json("config/stops.json"),
            trains=load_json("config/trains.json"),
            combine_similar_trains=load_json("config/combine_similar.json")
        ),
        Requester(key=load_text("config/key")),
        StopColors(stop_config)
    )

    r = c.get_status()

    print('\n'.join(map(str, r)))
