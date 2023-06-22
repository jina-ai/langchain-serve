class InvalidInstanceError(ValueError):
    def __init__(self, instance):
        super().__init__("Invalid instance: {}".format(instance))
        self.instance = instance


class InvalidAutoscaleMinError(ValueError):
    def __init__(self, min):
        super().__init__("Invalid autoscale.min: {}".format(min))
        self.min = min


class InvalidAutoscaleMaxError(ValueError):
    def __init__(self, max):
        super().__init__("Invalid autoscale.max: {}".format(max))
        self.max = max


class InvalidDiskSizeError(ValueError):
    def __init__(self, disk_size):
        super().__init__("Invalid disk size: {}".format(disk_size))
        self.disk_size = disk_size
