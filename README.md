# SUMO Dataset Generator

Synthetic dataset generator from SUMO simulations, developed as part of a master's thesis project and as an integration of the [S-LDM](https://github.com/DriveX-devs/S-LDM) research project.

The tool produces vehicle frame sequences with a multi-class label for each pack, useful for training machine learning models (in particular GNNs) aimed at detecting *triggering events* from S-LDM data. This approach is intended as an alternative/replacement for the previous ruleset-like deterministic system (e.g., "turn signal inserted → turn"). The reference GNN model is available in the [sldm-gnn](https://github.com/aledima00/sldm-gnn) repository.

---

## Requirements

- **Python** ≥ 3.13
- **uv** (Python package manager) or compatible `pip`
- **SUMO** installed and reachable from `PATH` (required by the `sumo` / `sumo-gui` binaries and by the `traci`/`sumolib` libraries)
- Python dependencies defined in `pyproject.toml`

> **Note:** the project depends on `traci>=1.24.0` and `sumolib>=1.24.0`. Make sure the installed SUMO binary version is compatible with these libraries.

---

## Dependency management with uv

The project uses **[uv](https://docs.astral.sh/uv/)** as its package manager. Compared to `pip`, `uv` provides faster and more reproducible dependency management, tracking the exact installed versions in the `uv.lock` file. This avoids conflicts with Python packages already installed at system level and ensures the development environment is identical across different machines.

To install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For more details and installation options, refer to the [official uv documentation](https://docs.astral.sh/uv/getting-started/installation/).

---

## Installation

The recommended way to set up the project is with **uv**:

```bash
git clone https://github.com/aledima00/sumo-dataset-generator.git
cd sumo-dataset-generator
uv sync
```

Alternatively, if you prefer `pip` inside a virtual environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Running the scripts

If you installed the project with **uv**, run the scripts directly using `uv run`. This command automatically uses the project-managed virtual environment without requiring manual activation:

```bash
uv run gen.py <scenario_path>
uv run sim.py -L <label> --outdir <output_dir> <scenario_path>
uv run lbstats.py <labels.parquet>
```

If you installed the project with **pip** inside a manually activated virtual environment, use `python` instead:

```bash
source .venv/bin/activate
python gen.py <scenario_path>
python sim.py -L <label> --outdir <output_dir> <scenario_path>
python lbstats.py <labels.parquet>
```

The two approaches are equivalent: `uv run` transparently resolves the project environment, while `source .venv/bin/activate` + `python` requires the environment to be active in the current shell.

---

## Repository structure

```text
.
├── gen.py                      # Entry point for route generation
├── sim.py                      # Entry point for running the simulation
├── lbstats.py                  # Utility for analyzing label distribution
├── genrouter/                  # Module for generating SUMO routes and vehicles
│   └── README.md               # Detailed genrouter documentation
├── sumodetector/               # Module for frame extraction and labeling
│   └── README.md               # Detailed sumodetector documentation
├── utils/                      # gparams schema
├── pyproject.toml              # Project configuration and dependencies
├── LICENSE                     # GPLv2
└── README.md                   # This file
```

For in-depth documentation on modules, classes, CLI options, and configuration parameters, see:

- [`genrouter/README.md`](genrouter/README.md)
- [`sumodetector/README.md`](sumodetector/README.md)

---

## Workflow

The workflow is divided into two main phases:

1. **Scenario preparation**: create a scenario folder containing the SUMO network (`map.net.xml`), the configuration file (`cfg.sumocfg`), and the generation parameters file (`gparams.yaml`).
2. **Dataset generation**: generate routes/vehicles and run the simulation to extract frame packs and their corresponding labels.

---

### 1. Prepare a scenario

> For the full list of generation parameters, see [`genrouter/README.md`](genrouter/README.md).

A minimal scenario requires:

```text
scenario/
├── map.net.xml        # SUMO road network
├── cfg.sumocfg        # Simulation configuration
└── gparams.yaml       # Vehicle and route generation parameters
```

The `cfg.sumocfg` file must specify at least:

- `input/net-file`: relative path to the network (`map.net.xml`)
- `input/route-files`: relative path to the routes file (e.g., `routes.rou.xml`, will be generated)
- `time/begin` and `time/end`: simulation duration
- `time/step-length`: simulation step length in seconds

Example:

```xml
<configuration>
  <input>
    <net-file value="map.net.xml"/>
    <route-files value="routes.rou.xml"/>
  </input>
  <time>
    <begin value="0"/>
    <end value="3600"/>
    <step-length value="0.1"/>
  </time>
</configuration>
```

The `gparams.yaml` file controls route and vehicle generation. For the full field documentation, see `utils/gparams-schema.json`. Main parameters:

```yaml
time: 3600          # total simulation time [s]
split: 1            # 1 = single simulation, >1 = split into independent sub-simulations
steplen: 0.1        # simulation step length [s]
nroutes: 100        # number of routes to generate
minrtlen: 10        # minimum route length [edges]
maxrtlen: 20        # maximum route length [edges]
vnum: 100           # number of vehicles to generate

vDrawMethod:
  name: "TimeMovingGaussian"   # vehicle insertion time drawing method
  tdevprop: 0.15                # standard deviation as a fraction of total simulation time
  onBorders: "Redistribute"     # redraw out-of-bounds values uniformly within range
  sigmaScaling: "Triangular"    # reduce variance near start/end of simulation

ClassParams:
  - name: "car"
    p: 1.0
    vClass: "passenger"

IndividualParams:
  - name: "normal"
    p: 1.0
    minGap: 2.5
    speedFactor: 1.0
    speedDev: 0.1
    lcGreediness: 0.5
    lcAggressiveness: 0.1
    jcAggressiveness: 0.1

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

---

### 2. Generate routes and vehicles

```bash
uv run gen.py <scenario_path>
```

This command:

- reads `gparams.yaml`
- overwrites `cfg.sumocfg` with time and step parameters
- generates the `routes.rou.xml` file with routes and vehicles

If `<scenario_path>` is a directory, it automatically looks for `gparams.yaml` and `cfg.sumocfg` inside it. If it is a `.yaml` file, it uses it directly.

---

### 3. Run the simulation and produce the dataset

> For the full list of simulation options and label detection details, see [`sumodetector/README.md`](sumodetector/README.md).

```bash
uv run sim.py -L <label> --outdir <output_dir> [options] <scenario_path>
```

Where `<label>` is the active label to extract:

| Value | Label |
|-------|-------|
| `0` | `LANE_CHANGE` |
| `1` | `OVERTAKE` |
| `2` | `TURN` |
| `3` | `COLLISION` |

Main options:

| Option | Description |
|--------|-------------|
| `-g`, `--gui` | Run SUMO with the GUI |
| `-W`, `--no-warnings` | Suppress SUMO warnings |
| `-E`, `--enable-emergency-insertions` | Enable emergency vehicle insertions |
| `-p`, `--pack-size` | Number of frames per pack (default: 20) |
| `--on-collision` | Action on collision: `teleport`, `warn`, `none`, `remove` |
| `--delay` | Delay in ms between simulation steps (useful with GUI) |
| `-T`, `--threads` | Number of parallel workers |
| `-S`, `--split` | Use `partN/` subfolders generated with `split > 1` |
| `--map-only` | Extract only the vector map (`vmap.parquet`) and exit |
| `--tar` | Create a `.tar` archive of the output folder |
| `-O`, `--opmode` | Pack building mode: `absolute`, `balanced`, `dense`, `sequential` (default: `absolute`) |

Example:

```bash
uv run sim.py -L 2 --outdir ./out/turn_eval --pack-size 20 -T 4 ./scenarios/turn/eval
```

---

## Output format

> For the full output schema and label encoding details, see [`sumodetector/README.md`](sumodetector/README.md).

The output folder contains the following Parquet files:

| File | Content |
|------|---------|
| `vmap.parquet` | Vector representation of the road network |
| `packs.parquet` | Vehicle frames grouped by `PackId` |
| `labels.parquet` | Multi-class labels (`MLBEncoded`) for each `PackId` |
| `vinfo.parquet` | Static information for each vehicle (dimensions, station type) |

The `packs.parquet` schema includes the fields:

- `VehicleId`, `X`, `Y`, `Speed`, `Angle`, `FrameId`, `PackId`

Labels are encoded as a bit mask in the `MLBEncoded` field:

- bit 0 → `LANE_CHANGE`
- bit 1 → `OVERTAKE`
- bit 2 → `TURN`
- bit 3 → `COLLISION`

---

## Complete example

The expected structure for examples is the following (to be populated under `examples/`):

```text
examples/
├── lane_change/
│   ├── train/
│   │   ├── map.net.xml
│   │   ├── cfg.sumocfg
│   │   └── gparams.yaml
│   ├── test/
│   └── eval/
├── overtake/
│   ├── train/
│   ├── test/
│   └── eval/
├── turn/
│   ├── train/
│   ├── test/
│   └── eval/
└── collision/
    ├── train/
    ├── test/
    └── eval/
```

Typical flow for a single configuration:

```bash
# 1. Generate routes and vehicles
uv run gen.py examples/turn/eval

# 2. Run the simulation to extract packs labeled as TURN
uv run sim.py -L 2 --outdir ./out/turn_eval --pack-size 20 -T 4 examples/turn/eval
```

---

## Additional utilities

### Label distribution analysis

```bash
uv run lbstats.py <labels.parquet>
```

Prints the total number of samples and the frequency of each label.

---

## Pack building modes (`--opmode`)

> For the complete buffering logic, see [`sumodetector/README.md`](sumodetector/README.md).

The `--opmode` parameter controls how packs are built when an event is detected:

- `absolute`: every trigger consumes/resets the current buffer, ensuring a labeled pack with the trigger frame as the last element.
- `balanced`: similar to `absolute`, but keeps one ready pack in the buffer.
- `dense`: each pack contains consecutive frames without flushing the buffer.
- `sequential`: packs are formed sequentially, one after another.

---

## Notes

- For long simulations or many vehicles, increase `-T` to parallelize extraction.
- When using `split > 1` in `gparams.yaml`, `gen.py` automatically creates `partN/` subfolders with balanced configurations and routes. Use the `-S` option during simulation.
- The `--map-only` option is useful to verify the network before launching a full simulation.

---

## License

This project is distributed under the [GNU General Public License v2](LICENSE).

## Links

- [S-LDM](https://github.com/DriveX-devs/S-LDM)
- [sldm-gnn](https://github.com/aledima00/sldm-gnn)
