from unittest.mock import mock_open, patch

import pytest

from lcserve.errors import InvalidAutoscaleMinError, InvalidInstanceError
from lcserve.config import validate_jcloud_config


def test_validate_jcloud_config():
    # Test with valid data
    valid_data = "instance: C1\nautoscale_min: 0\n"
    with patch("builtins.open", mock_open(read_data=valid_data)):
        assert validate_jcloud_config("path/to/valid_config.yaml") is None

    # Test with invalid instance
    invalid_instance_data = "instance: D1\nautoscale_min: 0\n"
    with patch("builtins.open", mock_open(read_data=invalid_instance_data)):
        with pytest.raises(InvalidInstanceError) as e:
            validate_jcloud_config("path/to/invalid_instance_config.yaml")
            assert e.instance == "D1"

    # Test with invalid autoscale_min
    invalid_autoscale_min_data = "instance: C1\nautoscale_min: -1\n"
    with patch("builtins.open", mock_open(read_data=invalid_autoscale_min_data)):
        with pytest.raises(InvalidAutoscaleMinError) as e:
            validate_jcloud_config("path/to/invalid_autoscale_min_config.yaml")
            assert str(e.min) == "-1"

    # Test with non-integer autoscale_min
    non_int_autoscale_min_data = "instance: C1\nautoscale_min: not_an_int\n"
    with patch("builtins.open", mock_open(read_data=non_int_autoscale_min_data)):
        with pytest.raises(InvalidAutoscaleMinError):
            validate_jcloud_config("path/to/non_int_autoscale_min_config.yaml")
            assert str(e.min) == "not_an_int"

    # Test with valid disk_size
    valid_disk_size_data = "instance: C1\nautoscale_min: 0\ndisk_size: 1G\n"
    with patch("builtins.open", mock_open(read_data=valid_disk_size_data)):
        assert validate_jcloud_config("path/to/valid_disk_size_config.yaml") is None

    # Test with invalid disk_size
    invalid_disk_size_data = "instance: C1\nautoscale_min: 0\ndisk_size: 1abc\n"
    with patch("builtins.open", mock_open(read_data=invalid_disk_size_data)):
        with pytest.raises(ValueError):
            validate_jcloud_config("path/to/invalid_disk_size_config.yaml")
            assert e.disk_size == "1GB"
