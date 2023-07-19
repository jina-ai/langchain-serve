import json

import click


@click.command()
@click.option(
    '--module',
    type=str,
    required=True,
)
@click.option(
    '--name',
    type=str,
    required=True,
)
@click.option(
    '--args',
    type=str,
    required=True,
)
def cli(module, name, args):
    import importlib

    from utils import fix_sys_path

    fix_sys_path()

    mod = importlib.import_module(module)
    getattr(mod, name)(**json.loads(args))


if __name__ == '__main__':
    cli()
