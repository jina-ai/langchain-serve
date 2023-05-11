import yaml
import click

from .errors import InvalidAutoscaleMinError, InvalidInstanceError


def validate_jcloud_config(config_path):
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)
        instance = config_data.get("instance")
        autoscale_min = config_data.get("autoscale_min")

        if instance and not (instance.startswith("C") and instance[1:].isdigit()):
            raise InvalidInstanceError(instance)

        if autoscale_min:
            try:
                autoscale_min_int = int(autoscale_min)
                if autoscale_min_int < 0:
                    raise InvalidAutoscaleMinError(autoscale_min)
            except ValueError:
                raise InvalidAutoscaleMinError(autoscale_min)


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

    return value
