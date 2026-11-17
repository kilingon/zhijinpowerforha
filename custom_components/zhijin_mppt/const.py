"""Constants for the ZhiJinPower MPPT integration."""

DOMAIN = "zhijin_mppt"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_SKIP_TEST = "skip_test"
CONF_ADAPTER = "adapter"  # Bluetooth adapter / proxy to use, or ADAPTER_AUTO
ADAPTER_AUTO = "auto"

# A failed poll keeps the last values; the entities only become unavailable after
# this many failed polls in a row. From then on the polling backs off, up to
# MAX_BACKOFF_INTERVAL seconds, so a controller that cannot be reached is not
# bothered with connection attempts all the time.
MAX_TOLERATED_FAILURES = 3
MAX_BACKOFF_INTERVAL = 300
# A Repairs issue is raised when the controller was unreachable this long (seconds).
REPAIR_AFTER = 180

# The controller accepts only one Bluetooth connection at a time. The integration
# connects briefly for every poll and disconnects again, so that the phone app can
# still be used between polls.
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 600

# Service UUID found in the advertisement of these controllers.
SERVICE_UUID_FF00 = "0000ff00-0000-1000-8000-00805f9b34fb"
