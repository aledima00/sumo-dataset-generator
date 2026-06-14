# sumodetector

`sumodetector` runs SUMO simulations via TraCI and extracts labeled vehicle frame packs. It detects triggering events (lane changes, overtakes, turns, collisions) and stores the results as Parquet files.

---

## Entry point

```bash
uv run sim.py -L <label> --outdir <output_dir> [options] <scenario_path>
```

`scenario_path` can be a directory containing `cfg.sumocfg` or the config file itself.

---

## CLI options

Required:

| Option | Description |
|--------|-------------|
| `-L, --label INTEGER` | Label to extract: `0` = LANE_CHANGE, `1` = OVERTAKE, `2` = TURN, `3` = COLLISION. |
| `--outdir PATH` | Output directory for the Parquet files. |

Flags:

| Flag | Description |
|------|-------------|
| `-g, --gui` | Run SUMO with the GUI. |
| `-W, --no-warnings` | Suppress SUMO warnings. |
| `-E, --enable-emergency-insertions` | Allow SUMO to insert vehicles in emergency situations. |
| `--map-only` | Extract only `vmap.parquet` and exit. |
| `--tar` | Archive the output directory into a `.tar` file. |
| `-S, --split` | Use `partN/` subfolders generated with `split > 1`. |

Parameters:

| Option | Default | Description |
|--------|---------|-------------|
| `-p, --pack-size INTEGER` | `20` | Number of frames per pack. |
| `--on-collision CHOICE` | `None` | Collision action: `teleport`, `warn`, `none`, `remove`. |
| `-d, --delay FLOAT` | `None` | Delay in ms between simulation steps (useful with GUI). |
| `-T, --threads INTEGER` | `1` | Number of parallel workers. |
| `-O, --opmode CHOICE` | `absolute` | Pack building mode: `absolute`, `balanced`, `dense`, `sequential`. |

---

## What it does

1. Resolves `cfg.sumocfg`.
2. Extracts the vector map from the network and saves `vmap.parquet`.
3. Unless `--map-only` is set, starts one or more SUMO processes via TraCI.
4. Each worker runs a portion of the simulation, detects events, and writes temporary Parquet files.
5. Merges worker outputs into `--outdir`.
6. Optionally archives the output folder with `--tar`.

---

## Detected labels

| Bit | Label | Trigger condition |
|-----|-------|-------------------|
| `0` | `LANE_CHANGE` | A vehicle changes lane within the same edge. |
| `1` | `OVERTAKE` | A vehicle passes its previous leader on the same edge. |
| `2` | `TURN` | A vehicle leaves a lane and does not continue on the straightest outgoing lane. |
| `3` | `COLLISION` | SUMO reports a collision. |

The label is stored as a bit mask in the `MLBEncoded` column of `labels.parquet`.

---

## Pack building modes (`--opmode`)

The `--opmode` controls how frames are grouped into packs when a trigger is detected:

| Mode | Behavior |
|------|----------|
| `absolute` | Trigger emits the last full pack and discards the rest of the buffer. The trigger frame is the last element of the labeled pack. |
| `balanced` | Like `absolute`, but keeps one ready pack in the buffer. |
| `dense` | Emits a pack whenever enough frames are available; no explicit trigger flush. |
| `sequential` | Packs are emitted strictly in order as the buffer fills. |

---

## Output files

| File | Description |
|------|-------------|
| `vmap.parquet` | Vector map of the road network. |
| `packs.parquet` | Vehicle frame packs. Columns: `VehicleId`, `X`, `Y`, `Speed`, `Angle`, `FrameId`, `PackId`. |
| `labels.parquet` | One row per `PackId` with the encoded multi-label. |
| `vinfo.parquet` | Static vehicle information: width, length, station type. |

---

## Multi-threading

Use `-T N` to run the simulation with `N` parallel workers:

- Without `-S`: the total simulation time is split into `N` contiguous slices.
- With `-S`: the module expects `part0/`, ..., `partN-1/` subfolders created by `genrouter` with `split > 1`, and runs each part independently.

At the end, outputs are merged and `PackId`s are adjusted so they remain unique across workers.
