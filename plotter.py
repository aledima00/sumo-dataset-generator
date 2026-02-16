import click
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import numpy as np
from shutil import rmtree

from sumodetector.map import MapParser


@click.group()
def cli():
    pass


@cli.command()
@click.argument("netfile_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def pmap(netfile_path:Path):
    """Plots a vectorial representation of SUMO map from the given .net.xml file."""
    parser = MapParser(str(netfile_path.resolve()))
    vmap_df = parser.asVectorDf()
    unique_eids = vmap_df["edge_id"].unique()
    map_eids = {eid:idx for idx, eid in enumerate(unique_eids)}
    vmap_df["eid_enc"] = vmap_df["edge_id"].map(map_eids).astype("uint32")
    vmap_df.drop(columns=["edge_id"], inplace=True)
    print(vmap_df)

    # plot the vmap with matplotlib
    outpath = netfile_path.resolve().parent / "vmap_plot.png"
    vmap_np = vmap_df[["start_x","start_y","end_x","end_y", "width"]].to_numpy()
    cmap = plt.get_cmap("tab20", len(unique_eids))
    colors = [cmap(eid_enc) for eid_enc in vmap_df["eid_enc"]]
    plt.figure(figsize=(10,10))
    for segment,color in zip(vmap_np,colors):
        plt.plot([segment[0], segment[2]], [segment[1], segment[3]], linewidth=segment[4],color=color)
    plt.title(f"Vector Map from {netfile_path.name}")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.axis("equal")
    plt.grid(True)
    plt.savefig(outpath, dpi=500)


@cli.command()
@click.option('--from', 'from_id', type=int, help='Starting Pack ID', required=True)
@click.option('--to', 'to_id', type=int, help='Ending Pack ID', required=True)
@click.argument('dirpath', type=click.Path(exists=True, dir_okay=True, file_okay=False))
def ppk(from_id:int, to_id:int, dirpath):
    dirpath = Path(dirpath).resolve()
    packs_path = dirpath / 'packs.parquet'
    labels_path = dirpath / 'labels.parquet'
    vinfo_path = dirpath / 'vinfos.parquet'

    outdir = dirpath / '.plots'
    if outdir.exists():
        rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    labels_df = None
    if labels_path.exists():
        print(f'labels.parquet found at {labels_path}')
        labels_df = pd.read_parquet(labels_path)


    for i in range(from_id, to_id + 1):
        if labels_df is not None:
            lb = labels_df[labels_df['PackId'] == i]
            lb = lb["MLBEncoded"].iloc[0].item()
            print(f'Labels for PackId {i}: {lb}')
        pkicall(i, packs_path, outdir, label=lb)
        

def pkicall(pckid:int,packs_path:Path, outdir:Path, *, label=None):
    """Process the pack parquet file and prints the series for one given Pack ID."""

    pkdataset = pq.ParquetFile(packs_path)
    nbatches = pkdataset.num_row_groups
    print(f'Number of row groups (batches): {nbatches}')

    nf = True
    for row in range(nbatches):
        df = pkdataset.read_row_group(row).to_pandas()
        if pckid in df['PackId'].values:
            print(f'PackId {pckid} found in row group {row}')
            nf = False
            break
    if nf:
        print(f'PackId {pckid} not found in any row group')
        return
    

    pack_df = df[df['PackId'] == pckid]
    #print(pack_df.head(10))

    if pack_df.empty:
        print(f'No data found for PackId {pckid}')
        return
    
    xmin = None
    xmax = None
    ymin = None
    ymax = None
    for vid, vgroup in pack_df.groupby('VehicleId'):
        #print(f'VehicleId: {vid}')
        xcoords = vgroup['X'].to_numpy()
        ycoords = vgroup['Y'].to_numpy()
        if xmin is None:
            xmin = xcoords.min()
            xmax = xcoords.max()
            ymin = ycoords.min()
            ymax = ycoords.max()
        else:
            xmin = min(xmin, xcoords.min())
            xmax = max(xmax, xcoords.max())
            ymin = min(ymin, ycoords.min())
            ymax = max(ymax, ycoords.max())
        t = np.arange(len(xcoords))
        plt.scatter(xcoords, ycoords,c=t, cmap='viridis', s=0.1)
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title(f'Vehicle Trajectories for PackId {pckid}')
    plt.colorbar(label='Time step')
    plt.axis('equal')
    plt.xlim(xmin-5, xmax+5)
    plt.ylim(ymin-5, ymax+5)
    fname = f'p{pckid}_map.png' if label is None else f'p{pckid}_map_l{label}.png'
    plt.savefig(outdir / fname, dpi=1000)
    plt.close()


if __name__ == "__main__":
    cli()