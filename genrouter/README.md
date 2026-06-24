# genrouter

`genrouter` generates SUMO route and vehicle files (`routes.rou.xml`) from a road network (`map.net.xml`) and a YAML configuration (`gparams.yaml`).

---

## Entry point

```bash
uv run gen.py <yfname>
```

`yfname` can be:

- a directory containing `gparams.yaml` and `cfg.sumocfg`
- a path to a `gparams.yaml` file directly

`gen.py` defines a Click command that builds a `GenerationController` (from `genrouter.controller`) and runs it. At the end it prints a summary (network file, simulation time, step length, number of routes and vehicles).

The command:

- reads `gparams.yaml`
- updates `cfg.sumocfg` with `time` and `step_len`
- generates `routes.rou.xml` in the same folder as `cfg.sumocfg`

If `split > 1` is set in `gparams.yaml`, the command creates `part0/`, `part1/`, ... subfolders, each with its own config and route file, splitting vehicles and simulation time evenly.

---

## Configuration (`gparams.yaml`)

For the JSON schema, see `utils/gparams-schema.json`.

### Main parameters

| Field | Description |
|-------|-------------|
| `time` | Total simulation time [s]. |
| `split` | Number of independent simulation parts (`1` = single run). |
| `steplen` | Simulation step length [s]. |
| `nroutes` | Number of routes to generate (defaults to `vnum`). |
| `minrtlen` | Minimum route length [edges]. |
| `maxrtlen` | Maximum route length [edges]. |
| `vnum` | Number of vehicles to generate. |
| `source_edges` | Optional list of starting edge IDs. If empty, routes start from edges with no incoming connections. |
| `vDrawMethod` | How vehicle departure times are sampled. |
| `ClassParams` | Distribution of SUMO vehicle classes (e.g., `passenger`, `truck`). |
| `IndividualParams` | Distribution of driver behavior parameter sets. |
| `VehicleParams` | Distribution of physical vehicle parameter sets. |
| `Modifiers` | Optional random behavioral modifiers. |

### Departure time methods (`vDrawMethod`)

#### `Uniform`

```yaml
vDrawMethod:
  name: "Uniform"
```

Departures sampled uniformly in `[0, time]`.

#### `FixedAbsGaussian`

```yaml
vDrawMethod:
  name: "FixedAbsGaussian"
  tdevprop: 0.15
  onBorders: "Redistribute"   # or "Clamp"
```

Gaussian centered at `0` with `sigma = time * tdevprop`; absolute value is taken. Out-of-range values are redistributed or clamped.

#### `TimeMovingGaussian`

```yaml
vDrawMethod:
  name: "TimeMovingGaussian"
  tdevprop: 0.15
  onBorders: "Redistribute"
  sigmaScaling: "Triangular"   # or "None" / "Quadratic"
```

Gaussian mean moves linearly across the simulation time; variance can be reduced near the boundaries with `sigmaScaling`.

### Parameter set items

All `ClassParams`, `IndividualParams`, and `VehicleParams` items must define:

- `name`: identifier
- `p`: relative weight (normalized automatically to sum to 1)
- class/behavior/vehicle-specific fields

`ClassParams` example:

```yaml
ClassParams:
  - name: "car"
    p: 1.0
    vClass: "passenger"
```

`IndividualParams` example:

```yaml
IndividualParams:
  - name: "normal"
    p: 1.0
    minGap: 2.5
    speedFactor: 1.0
    speedDev: 0.1
    lcGreediness: 0.5
    lcAggressiveness: 0.1
    jcAggressiveness: 0.1
```

`VehicleParams` example:

```yaml
VehicleParams:
  - name: "car"
    p: 1.0
    stType: 5
    accel: 2.6
    decel: 4.5
    emergency_decel: 9.0
    length_m: 5.0
    width_m: 1.8
    max_speed: 180.0
    gui_shape: "passenger"
```

### Modifiers

Modifiers are applied to a vehicle with probability `p`.

#### `DISTRACTED_DRIVER`

```yaml
Modifiers:
  - name: "DISTRACTED_DRIVER"
    p: 0.1
    reactionTimeAvg: 1.0
    reactionTimeDev: 0.2
```

Increases the driver's reaction time (`actionStepLength`) by sampling from a Gaussian.

#### `UNEXPECTED_DECEL`

```yaml
Modifiers:
  - name: "UNEXPECTED_DECEL"
    p: 0.1
    decelPropAvg: 0.5
    decelPropDev: 0.1
```

Reduces the vehicle's `apparentDecel` relative to its real `decel`, making it brake less effectively than expected.

---

## Output

The generated `routes.rou.xml` contains:

```xml
<routes>
  <route id="RT0" edges="..."/>
  ...
  <vType id="ST005_car_normal_car" .../>
  ...
  <vehicle id="veh0" type="..." depart="..." route="..."/>
  ...
</routes>
```

Vehicle IDs are sorted by departure time.
