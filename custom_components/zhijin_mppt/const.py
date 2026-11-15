"""Constants for the ZhiJinPower MPPT integration."""

DOMAIN = "zhijin_mppt"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_SKIP_TEST = "skip_test"

# The controller accepts only one Bluetooth connection at a time. The integration
# connects briefly for every poll and disconnects again, so that the phone app can
# still be used between polls.
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 600

# Service UUID found in the advertisement of these controllers.
SERVICE_UUID_FF00 = "0000ff00-0000-1000-8000-00805f9b34fb"
