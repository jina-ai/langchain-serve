import yaml

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
