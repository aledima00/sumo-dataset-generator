import click
from pathlib import Path

from colorama import Fore as _Fore, Style as _Style

from genrouter import GenerationController as GenCtl


@click.command()
@click.argument('yfname', required=True, type=click.Path(exists=True, dir_okay=True, file_okay=True, path_type=Path))
def console(yfname: Path):
    genctl = GenCtl(yfname=yfname)
    try:
        result = genctl.run()
    except Exception as e:
        click.echo(f"{_Fore.RED}Error during generation, exiting ... {_Style.RESET_ALL}:\n{e}")
        return

    click.echo(f"{_Fore.CYAN}[generation parameters loaded from './{result['yfname']}']{_Style.RESET_ALL}")
    prints = [
        ("INPUT NETWORK FILE", result["net_file"]),
        ("TOTAL SIMULATION TIME (S)", result["time"]),
        ("SIMULATION STEP LENGTH (S)", result["steplen"]),
        ("NUM. OF ROUTES", result["nroutes"]),
        ("NUM. OF VEHICLES", result["vnum"]),
    ]
    click.echo(f"{_Fore.GREEN}Generation completed successfully!{_Style.RESET_ALL}" + "".join([f"\n{_Fore.YELLOW}  - {k}{_Style.RESET_ALL}: {v}" for k, v in prints]))


if __name__ == "__main__":
    console()
