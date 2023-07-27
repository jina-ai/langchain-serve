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
    '--param',
    type=(str, str),
    multiple=True,
    required=True,
)
def cli(module, name, param):
    import importlib

    from utils import fix_sys_path

    fix_sys_path()

    mod = importlib.import_module(module)
    getattr(mod, name)(**dict(param))


if __name__ == '__main__':
    cli()
