import os
from dataclasses import dataclass, field
from typing import Dict

import click
import yaml

from .errors import (
    InvalidAutoscaleMaxError,
    InvalidAutoscaleMinError,
    InvalidDiskSizeError,
    InvalidInstanceError,
)

INSTANCE = 'instance'
AUTOSCALE_MIN = 'autoscale_min'
AUTOSCALE_MAX = 'autoscale_max'
DISK_SIZE = 'disk_size'
JCloudConfigFile = 'jcloud_config.yml'
DEFAULT_TIMEOUT = 120
DEFAULT_DISK_SIZE = '1G'


@dataclass
class Defaults:
    instance: str = 'C3'
    autoscale_min: int = 1
    autoscale_max: int = 10
    autoscale_rps: int = 10
    autoscale_stable_window: int = DEFAULT_TIMEOUT
    autoscale_revision_timeout: int = DEFAULT_TIMEOUT
    disk_size: str = DEFAULT_DISK_SIZE

    def __post_init__(self):
        _path = os.path.join(os.getcwd(), JCloudConfigFile)
        if os.path.exists(_path):
            # read from config yaml
            with open(_path, 'r') as fp:
                config = yaml.safe_load(fp.read())
                self.instance = config.get('instance', self.instance)
                self.autoscale_min = config.get('autoscale', {}).get(
                    'min', self.autoscale_min
                )
                self.autoscale_max = config.get('autoscale', {}).get(
                    'max', self.autoscale_max
                )
                self.autoscale_rps = config.get('autoscale', {}).get(
                    'rps', self.autoscale_rps
                )
                self.autoscale_stable_window = config.get('autoscale', {}).get(
                    'stable_window', self.autoscale_stable_window
                )
                self.autoscale_revision_timeout = config.get('autoscale', {}).get(
                    'revision_timeout', self.autoscale_revision_timeout
                )
                self.disk_size = config.get('disk_size', self.disk_size)


@dataclass
class AutoscaleConfig:
    min: int = Defaults.autoscale_min
    max: int = Defaults.autoscale_max
    rps: int = Defaults.autoscale_rps
    stable_window: int = Defaults.autoscale_stable_window
    revision_timeout: int = Defaults.autoscale_revision_timeout

    def to_dict(self) -> Dict:
        return {
            'autoscale': {
                'min': self.min,
                'max': self.max,
                'metric': 'rps',
                'target': self.rps,
                'stable_window': self.stable_window,
                'revision_timeout': self.revision_timeout,
            }
        }


@dataclass
class JCloudConfig:
    is_websocket: bool
    timeout: int = DEFAULT_TIMEOUT
    instance: str = Defaults.instance
    disk_size: str = Defaults.disk_size
    autoscale: AutoscaleConfig = field(init=False)

    def __post_init__(self):
        self.autoscale = AutoscaleConfig(
            stable_window=self.timeout, revision_timeout=self.timeout
        )

    def to_dict(self) -> Dict:
        jcloud_dict = {
            'jcloud': {
                'expose': True,
                'resources': {
                    'instance': self.instance,
                    'capacity': 'spot',
                },
                'healthcheck': not self.is_websocket,
                'timeout': self.timeout,
                **self.autoscale.to_dict(),
            }
        }

        # Don't add the volume block if self.disk_size is 0
        if isinstance(self.disk_size, str):
            jcloud_dict['jcloud']['resources']['storage'] = {
                'kind': 'efs',
                'size': self.disk_size,
            }

        return jcloud_dict


def validate_jcloud_config(config_path):
    with open(config_path, "r") as f:
        config_data: Dict = yaml.safe_load(f)
        instance: str = config_data.get(INSTANCE)
        autoscale_min: str = config_data.get(AUTOSCALE_MIN)
        autoscale_max: str = config_data.get(AUTOSCALE_MAX)
        disk_size: str = config_data.get(DISK_SIZE)

        if instance and not (
            instance.startswith(("C", "G")) and instance[1:].isdigit()
        ):
            raise InvalidInstanceError(instance)

        if autoscale_min:
            try:
                autoscale_min_int = int(autoscale_min)
                if autoscale_min_int < 0:
                    raise InvalidAutoscaleMinError(autoscale_min)
            except ValueError:
                raise InvalidAutoscaleMinError(autoscale_min)

        if autoscale_max:
            try:
                autoscale_max_int = int(autoscale_max)
                if autoscale_max_int < 0:
                    raise InvalidAutoscaleMaxError(autoscale_max)
            except ValueError:
                raise InvalidAutoscaleMaxError(autoscale_max)

        if disk_size is not None:
            if (
                isinstance(disk_size, str)
                and not disk_size.endswith(("M", "MB", "Mi", "G", "GB", "Gi"))
            ) or (isinstance(disk_size, int) and disk_size != 0):
                raise InvalidDiskSizeError(disk_size)


def validate_jcloud_config_callback(ctx, param, value):
    if not value:
        return None
    try:
        validate_jcloud_config(value)
    except InvalidInstanceError as e:
        raise click.BadParameter(
            f"Invalid instance '{e.instance}' found in config file', please refer to https://docs.jina.ai/concepts/jcloud/configuration/#cpu-tiers for instance definition."
        )
    except InvalidAutoscaleMinError as e:
        raise click.BadParameter(
            f"Invalid instance '{e.min}' found in config file', it should be a number >= 0."
        )
    except InvalidDiskSizeError as e:
        raise click.BadParameter(
            f"Invalid disk size '{e.disk_size}' found in config file."
        )

    return value


def resolve_jcloud_config(config, module_dir: str):
    # config given from CLI takes higher priority
    if config:
        return config

    # Check to see if jcloud YAML/YML file exists at app dir
    config_path_yml = os.path.join(module_dir, "jcloud.yml")
    config_path_yaml = os.path.join(module_dir, "jcloud.yaml")

    if os.path.exists(config_path_yml):
        config_path = config_path_yml
    elif os.path.exists(config_path_yaml):
        config_path = config_path_yaml
    else:
        return None

    try:
        validate_jcloud_config(config_path)
    except (InvalidAutoscaleMinError, InvalidInstanceError, InvalidDiskSizeError):
        # If it's malformed, we treated as non-existed
        return None

    print(f'JCloud config file at app directory will be applied: {config_path}')
    return config_path


def get_jcloud_config(
    config_path: str = None, timeout: int = DEFAULT_TIMEOUT, is_websocket: bool = False
) -> JCloudConfig:
    jcloud_config = JCloudConfig(is_websocket=is_websocket, timeout=timeout)
    if not config_path:
        return jcloud_config

    if not os.path.exists(config_path):
        print(f'config file {config_path} not found')
        return jcloud_config

    with open(config_path, 'r') as f:
        config_data: Dict = yaml.safe_load(f)
        if not config_data:
            return jcloud_config

        instance = config_data.get(INSTANCE)
        autoscale_min = config_data.get(AUTOSCALE_MIN)
        autoscale_max = config_data.get(AUTOSCALE_MAX)
        disk_size = config_data.get(DISK_SIZE)

        if instance:
            jcloud_config.instance = instance
        if autoscale_min is not None:
            jcloud_config.autoscale.min = autoscale_min
        if autoscale_max is not None:
            jcloud_config.autoscale.max = autoscale_max
        if disk_size is not None:
            jcloud_config.disk_size = disk_size

    return jcloud_config
