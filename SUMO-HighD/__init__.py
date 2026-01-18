import traci as _traci
import json as _json
import math as _math
from collections import defaultdict as _defdict
import matplotlib.pyplot as _plt
import numpy as _np

# Lane change direction: 1 - left, -1 - right

ROUTES = ["est_to_west", "west_to_est"]
RED_RGBA = (255, 0, 0, 255)
PURPLE_RGBA = (128, 0, 128, 255)
GREEN_RGBA = (0, 128, 0, 255)
BLUE_RGBA = (0, 0, 255, 255)

YELLOW_RGBA = (255, 255, 0, 255)

SPEED_LIMIT = 55
LANE_LENGTH = 410
LENGTH_THRESHOLD = 10

VEHICLES_TO_COLOR = dict()

def manually_move_veh(veh, time_dict, frame, delta_pos_dict):
    x, y = _traci.vehicle.getPosition(veh)
    if frame not in delta_pos_dict[veh].keys():
        return
    delta_x, delta_y = delta_pos_dict[veh][frame]
    route = None
    driving_direction = time_dict[frame][veh]["driving_direction"]
    if driving_direction == "right":
        route = ROUTES[0]
    else:
        route = ROUTES[1]
    lane = time_dict[frame][veh]["lane_id"] - 1 if time_dict[frame][veh]["lane_id"] <= 3 else time_dict[frame][veh]["lane_id"] - 4
    # _traci.vehicle.moveTo(veh, route.replace("_to_", "_") + "_" + str(int(lane)), x - delta_x)
    _traci.vehicle.moveToXY(veh, route, time_dict[frame][veh]["lane_id"], x - delta_x, y + delta_y, keepRoute=0)

def update_delta_pos_dict(delta_pos_dict, time_dict, veh):
    for i, f in enumerate(time_dict.keys()):
        if i == 0:
            continue
        prev_frame = list(time_dict.keys())[i-1]
        if veh not in time_dict[prev_frame].keys():
            continue
        if veh in time_dict[f].keys():
            if veh not in delta_pos_dict.keys():
                delta_pos_dict[veh] = dict()
            delta_pos_dict[veh][f] = (time_dict[f][veh]["x"] - time_dict[prev_frame][veh]["x"], time_dict[f][veh]["y"] - time_dict[prev_frame][veh]["y"])
        else:
            break

def calculate_cost_over_time(data, frame, vehicle_id):
    global VEHICLES_TO_COLOR
    costs = _defdict(list)
    start_frame = frame
    end_frame = frame + 10
    for f in range(start_frame, end_frame):
        if vehicle_id not in data[f].keys():
            costs["preceding"].append(0)
            costs["following"].append(0)
            costs["left_preceding"].append(0)
            costs["left_following"].append(0)
            costs["right_preceding"].append(0)
            costs["right_following"].append(0)
            costs["left_alongside"].append(0)
            costs["right_alongside"].append(0)
            continue
        d = data[f][vehicle_id]
        if d["preceding_id"] != 0:
            id = str(d["preceding_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, PURPLE_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = PURPLE_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["preceding"].append(cost)
        else:
            costs["preceding"].append(0)
        if d["following_id"] != 0:
            id = str(d["following_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, GREEN_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = GREEN_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["following"].append(cost)
        else:
            costs["following"].append(0)
        if d["left_preceding_id"] != 0:
            id = str(d["left_preceding_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, PURPLE_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = PURPLE_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["left_preceding"].append(cost)
        else:
            costs["left_preceding"].append(0)
        if d["left_following_id"] != 0:
            id = str(d["left_following_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, GREEN_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = GREEN_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["left_following"].append(cost)
        else:
            costs["left_following"].append(0)
        if d["right_preceding_id"] != 0:
            id = str(d["right_preceding_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, PURPLE_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = PURPLE_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["right_preceding"].append(cost)
        else:
            costs["right_preceding"].append(0)
        if d["right_following_id"] != 0:
            id = str(d["right_following_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, GREEN_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = GREEN_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["right_following"].append(cost)
        else:
            costs["right_following"].append(0)
        if d["left_alongside_id"] != 0:
            id = str(d["left_alongside_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, BLUE_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = BLUE_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["left_alongside"].append(cost)
        else:
            costs["left_alongside"].append(0)
        if d["right_alongside_id"] != 0:
            id = str(d["right_alongside_id"])
            if id in _traci.vehicle.getIDList():
                _traci.vehicle.setColor(id, BLUE_RGBA)
            else:
                VEHICLES_TO_COLOR[id] = BLUE_RGBA
            distance = _math.sqrt((d["x"] - data[f][id]["x"])**2 + (d["y"] - data[f][id]["y"])**2)
            relative_speed = abs(d["x_velocity"] - data[f][id]["x_velocity"])
            if relative_speed == 0:
                relative_speed = 0.01
            cost = - (distance / relative_speed)
            costs["right_alongside"].append(cost)
        else:
            costs["right_alongside"].append(0)
    return costs

def get_next_lane_change(time_dict, current_frame, vehicle_id):
    """Look ahead to find the next lane change for a vehicle"""
    current_lane = None
    frames = sorted(time_dict.keys())
    current_idx = frames.index(current_frame)
    
    for frame in frames[current_idx:]:
        if vehicle_id in time_dict[frame]:
            if current_lane is None:
                current_lane = time_dict[frame][vehicle_id]["lane_id"]
            elif time_dict[frame][vehicle_id]["lane_id"] != current_lane:
                lane = time_dict[frame][vehicle_id]["lane_id"]
                driving_direction = time_dict[frame][vehicle_id]["driving_direction"]
                if driving_direction == "right":
                    lane = lane - 4
                else:
                    lane = lane - 1
                if lane > 2:
                    if current_lane != 2:
                        return frame, 2
                    else:
                        continue
                elif lane < 0:
                    if current_lane != 0:
                        return frame, 0
                    else:
                        continue
                else:
                    return frame, lane
    return None, None

def add_vehicle(veh, driving_direction, x_velocity, lane_id, x):
    vehicleID = veh
    route = None
    lane = None
    if driving_direction == "right":
        route = ROUTES[1]
        lane = lane_id - 4
        if lane > 2:
            lane = 2
        if lane > 2:
            lane = 2
    else:
        route = ROUTES[0]
        lane = lane_id - 1
        if lane < 0:
            lane = 0
        if lane > 2:
            lane = 2
    
    if x_velocity > SPEED_LIMIT:
        x_velocity = SPEED_LIMIT
    _traci.vehicle.add(vehicleID, route, departLane=int(lane), departPos="base", departSpeed=str(x_velocity))
    lane_str = route.replace("_to_", "_") + "_" + str(int(lane))
    if route == "est_to_west" and x < LANE_LENGTH - LENGTH_THRESHOLD:
        _traci.vehicle.moveTo(vehicleID, lane_str, LANE_LENGTH - x)
    elif route == "west_to_est" and x > LENGTH_THRESHOLD:
        _traci.vehicle.moveTo(vehicleID, lane_str, x)
    _traci.vehicle.setLaneChangeMode(vehicleID, 0)

def create_time_dict(data):
    time_dict = dict()
    frames = set()
    for k in data.keys():
        for f in data[k]["frame"]:
            frames.add(f)

    # Collect one frame every 3 frames to reduce the sampling rate from 25 to circa 10 frames per second
    tmp_frames = list()
    i = 0
    for f in frames:
        if i == 0:
            tmp_frames.append(f)
            i += 1
        elif i < 3:
            i += 1
        else:
            i = 0

    frames = tmp_frames
    counter = 0
    for f in frames:
        time_dict[counter] = dict()
        for k in data.keys():
            if f in data[k]["frame"]:
                time_dict[counter][k] = dict()
                frame_index = data[k]["frame"].index(f)
                time_dict[counter][k]["lane_change"] = data[k]["laneChange"]
                time_dict[counter][k]["driving_direction"] = data[k]["drivingDirection"]
                time_dict[counter][k]["x"] = data[k]["x"][frame_index]
                time_dict[counter][k]["y"] = data[k]["y"][frame_index]
                time_dict[counter][k]["x_velocity"] = data[k]["xVelocity"][frame_index]
                time_dict[counter][k]["lane_id"] = data[k]["laneId"][frame_index]
                time_dict[counter][k]["preceding_id"] = data[k]["precedingId"][frame_index]
                time_dict[counter][k]["following_id"] = data[k]["followingId"][frame_index]
                time_dict[counter][k]["left_preceding_id"] = data[k]["leftPrecedingId"][frame_index]
                time_dict[counter][k]["left_following_id"] = data[k]["leftFollowingId"][frame_index]
                time_dict[counter][k]["right_preceding_id"] = data[k]["rightPrecedingId"][frame_index]
                time_dict[counter][k]["right_following_id"] = data[k]["rightFollowingId"][frame_index]
                time_dict[counter][k]["left_alongside_id"] = data[k]["leftAlongsideId"][frame_index]
                time_dict[counter][k]["right_alongside_id"] = data[k]["rightAlongsideId"][frame_index]
        counter += 1
    
    return time_dict

def main():
    global VEHICLES_TO_COLOR
    costs_collection = _defdict(list)
    for i in range(2, 3):
        _traci.start(["sumo-gui", "-c", "highway.sumo.cfg", "--collision.action", "warn", "--lanechange.duration", "1"])
        print(f"\nStarting simulation for file {i} ...\n")
        file = f"data/0{i}_newTracks.json" if i < 10 else f"data/{i}_newTracks.json"
        data = None
        with open(file) as f:
            data = _json.load(f)

        # Set this variable to True to move the vehicles manually using the (x, y) data from the JSON file
        # Default is False to let SUMO handle the vehicle movement by just setting the speed
        move_veh = False
        
        time_dict = create_time_dict(data)
        already_present = set()
        lc_dict = dict()
        delta_pos_dict = dict()
        current_time = 0
        
        for frame in time_dict.keys():
            for veh in time_dict[frame].keys():
                if veh not in already_present:
                    # Add vehicle to the simulation
                    add_vehicle(veh, time_dict[frame][veh]["driving_direction"], time_dict[frame][veh]["x_velocity"], time_dict[frame][veh]["lane_id"], time_dict[frame][veh]["x"])
                    already_present.add(veh)
                    if move_veh:
                        update_delta_pos_dict(delta_pos_dict, time_dict, veh)
                    if veh in VEHICLES_TO_COLOR:
                        _traci.vehicle.setColor(veh, VEHICLES_TO_COLOR[veh])
                        VEHICLES_TO_COLOR.pop(veh)
                    # print(f"Vehicle {veh} added")
                else:
                    vehicles = _traci.vehicle.getIDList()
                    if veh not in vehicles:
                        # Handle the case where vehicle is no longer present in the simulation but is still present in the JSON file
                        continue
                    x_velocity = time_dict[frame][veh]["x_velocity"]
                    # Limit the speed to 55 m/s
                    if x_velocity > SPEED_LIMIT:
                        x_velocity = SPEED_LIMIT
                    _traci.vehicle.setSpeed(veh, x_velocity)
                    if move_veh:
                        manually_move_veh(veh, time_dict, frame, delta_pos_dict)
                    if veh in lc_dict.keys():
                        next_time, next_lane = lc_dict[veh]
                        # If the vehicle is scheduled to start changing lane at the current frame, change the lane
                        if next_time == current_time:
                            costs = calculate_cost_over_time(time_dict, frame, veh)
                            for k in costs.keys():
                                costs_collection[k].append(costs[k])
                            _traci.vehicle.changeLane(veh, next_lane, 1)
                            # print(f"Vehicle {veh} is changing lane")
                    if time_dict[frame][veh]["lane_change"] != 0:
                        # Get frame and lane for lane change direction
                        next_frame, next_lane = get_next_lane_change(time_dict, frame, veh)
                        if next_frame and next_lane:
                            _traci.vehicle.setColor(veh, RED_RGBA)
                            if veh not in lc_dict.keys() or next_lane != lc_dict[veh][1]:
                                # 10 frames per second, so divide by 10 to get the time in seconds
                                next_time = next_frame / 10
                                # Schedule 1 second before the actual lane change
                                next_time -= 1 
                                if next_time < current_time:
                                    next_time = current_time + 0.1
                                next_time = float("{:.1f}".format(next_time))
                                # Store the next time and lane for lane change
                                lc_dict[veh] = (next_time, next_lane)
            _traci.simulationStep()
            current_time = _traci.simulation.getTime()

    for i, k in enumerate(costs_collection.keys()):
        median = list()
        for x in zip(*costs_collection[k]):
            x = [i for i in x if i != 0]
            median.append(_np.median(x))
        _plt.plot(median, label=k)
        _plt.title(f"Median cost for {k} over time (cost = " + r"$-\frac{distance}{relative_speed}$" + ")")
        _plt.ylabel("Cost")
        _plt.xlabel("Time [s]")
        _plt.legend()
        _plt.savefig(f"plots/{k}.png")
        _plt.close()

    _traci.close()

if __name__ == "__main__":
    main()