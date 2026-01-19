import traci as _traci
import json as _json
from pathlib import Path as _Path
from typing import Literal as _Lit

# Lane change direction: 1 - left, -1 - right

ROUTES = ["est_to_west", "west_to_est"]

SPEED_LIMIT = 55
LANE_LENGTH = 410
LENGTH_THRESHOLD = 10

def _manually_move_veh(veh, time_dict, frame, delta_pos_dict):
    """
    Moves a vehicle to a specific (x, y) position based on precomputed delta positions.
    
    :param veh: Vehicle ID
    :param time_dict: Dictionary containing vehicle data over time
    :param frame: Current frame number
    :param delta_pos_dict: Dictionary containing precomputed delta positions for vehicles
    """
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
    # lane = time_dict[frame][veh]["lane_id"] - 1 if time_dict[frame][veh]["lane_id"] <= 3 else time_dict[frame][veh]["lane_id"] - 4
    # _traci.vehicle.moveTo(veh, route.replace("_to_", "_") + "_" + str(int(lane)), x - delta_x)
    _traci.vehicle.moveToXY(veh, route, time_dict[frame][veh]["lane_id"], x - delta_x, y + delta_y, keepRoute=0)

def _update_delta_pos_dict(delta_pos_dict, time_dict, veh):
    """
    Precomputes the delta positions for a vehicle between consecutive frames.
    The delta positions are computed as the difference in (x, y) coordinates between consecutive frames.

    :param delta_pos_dict: Dictionary to store delta positions
    :param time_dict: Dictionary containing vehicle data over time
    :param veh: Vehicle ID
    """
    # compare positions between consecutive frames
    for i, f in enumerate(time_dict.keys()):
        if i == 0:
            continue # Skip if no previous frame
        prev_frame = list(time_dict.keys())[i-1]
        if veh not in time_dict[prev_frame].keys():
            continue # Skip if vehicle not present in previous frame

        if veh in time_dict[f].keys():
            if veh not in delta_pos_dict.keys():
                delta_pos_dict[veh] = dict()
            delta_pos_dict[veh][f] = (time_dict[f][veh]["x"] - time_dict[prev_frame][veh]["x"], time_dict[f][veh]["y"] - time_dict[prev_frame][veh]["y"])
        else:
            break # Stop if vehicle is no longer present

def _get_next_lane_change(time_dict, current_frame, vehicle_id):
    """
    Look ahead in the time_dict to find the next lane change for a given vehicle.

    :param time_dict: Dictionary containing vehicle data over time
    :param current_frame: Current frame number
    :param vehicle_id: Vehicle ID
    :return: Tuple of (next_frame, next_lane) where next_frame is the frame number of the lane change and next_lane is the target lane ID, or (None, None) if no lane change is found
    """
    current_lane = None
    frames = sorted(time_dict.keys())
    current_idx = frames.index(current_frame)
    
    # loop on future frames only
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

def _add_vehicle(veh, driving_direction: _Lit["right", "left"], x_velocity, lane_id, x):
    """
    Adds a vehicle to the SUMO simulation with specified parameters.

    :param veh: Vehicle ID
    :param driving_direction: Direction of driving ("right" or "left"), used to choose the route
    :param x_velocity: Initial velocity of the vehicle in the driving direction
    :param lane_id: Lane ID from the JSON data
    :param x: Initial x position of the vehicle along the lane
    """
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
    """
    Creates a time-based dictionary loading vehicle data from the json input file.

    :param data: Dictionary containing vehicle data loaded from JSON
    """
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
    for cnt,f in enumerate(frames):
        time_dict[cnt] = dict()
        for k in data.keys():
            if f in data[k]["frame"]:
                time_dict[cnt][k] = dict()
                frame_index = data[k]["frame"].index(f)
                time_dict[cnt][k]["lane_change"] = data[k]["laneChange"]
                time_dict[cnt][k]["driving_direction"] = data[k]["drivingDirection"]
                time_dict[cnt][k]["x"] = data[k]["x"][frame_index]
                time_dict[cnt][k]["y"] = data[k]["y"][frame_index]
                time_dict[cnt][k]["x_velocity"] = data[k]["xVelocity"][frame_index]
                time_dict[cnt][k]["lane_id"] = data[k]["laneId"][frame_index]
                time_dict[cnt][k]["preceding_id"] = data[k]["precedingId"][frame_index]
                time_dict[cnt][k]["following_id"] = data[k]["followingId"][frame_index]
                time_dict[cnt][k]["left_preceding_id"] = data[k]["leftPrecedingId"][frame_index]
                time_dict[cnt][k]["left_following_id"] = data[k]["leftFollowingId"][frame_index]
                time_dict[cnt][k]["right_preceding_id"] = data[k]["rightPrecedingId"][frame_index]
                time_dict[cnt][k]["right_following_id"] = data[k]["rightFollowingId"][frame_index]
                time_dict[cnt][k]["left_alongside_id"] = data[k]["leftAlongsideId"][frame_index]
                time_dict[cnt][k]["right_alongside_id"] = data[k]["rightAlongsideId"][frame_index]
    
    return time_dict

def runTrack(i:int):
    # _traci.start(["sumo-gui", "-c", "highway.sumo.cfg", "--collision.action", "warn", "--lanechange.duration", "1"])
    print(f"\nReproducing Trace {i} from SUMO-HighD...\n")
    _thisfile_path = _Path(__file__).resolve()
    file = str((_thisfile_path.parent / "data" / f"{i:02d}_newTracks.json").resolve())
    data = None
    with open(file) as f:
        data = _json.load(f)

    # Set this variable to True to move the vehicles manually using the (x, y) data from the JSON file
    # Default is False to let SUMO handle the vehicle movement by just setting the speed
    move_veh = True
    
    time_dict = create_time_dict(data)
    already_present = set()
    lc_dict = dict()
    delta_pos_dict = dict()
    current_time = 0
    
    for frame in time_dict.keys():
        for veh in time_dict[frame].keys():
            if veh not in already_present:
                # Add vehicle to the simulation
                _add_vehicle(veh, time_dict[frame][veh]["driving_direction"], time_dict[frame][veh]["x_velocity"], time_dict[frame][veh]["lane_id"], time_dict[frame][veh]["x"])
                already_present.add(veh)
                if move_veh:
                    _update_delta_pos_dict(delta_pos_dict, time_dict, veh)
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
                    _manually_move_veh(veh, time_dict, frame, delta_pos_dict)
                if veh in lc_dict.keys():
                    next_time, next_lane = lc_dict[veh]
                    # If the vehicle is scheduled to start changing lane at the current frame, change the lane
                    if next_time == current_time:
                        _traci.vehicle.changeLane(veh, next_lane, 1)
                        # print(f"Vehicle {veh} is changing lane")
                if time_dict[frame][veh]["lane_change"] != 0:
                    # Get frame and lane for lane change direction
                    next_frame, next_lane = _get_next_lane_change(time_dict, frame, veh)
                    if next_frame and next_lane:
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

    _traci.close()

__all__ = ["runTrack"]