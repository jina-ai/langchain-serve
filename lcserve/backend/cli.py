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
@click.option('--params', type=str)
def cli(module, name, params):
    import importlib

    from utils import fix_sys_path

    fix_sys_path()

    inputs = {}
    if params:
        inputs = json.loads(params)

    mod = importlib.import_module(module)
    getattr(mod, name)(**dict(inputs))


if __name__ == '__main__':
    cli()
