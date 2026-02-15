"""Constants for the Appliance Status Monitor integration."""

DOMAIN = "appliance_status"

# Config entry keys
CONF_APPLIANCE_NAME = "appliance_name"
CONF_POWER_ENTITY = "power_entity"
CONF_ENERGY_ENTITY = "energy_entity"

# Default values (from Node-RED logic analysis)
DEFAULT_STANDBY_THRESHOLD = 2.0      # Watts
DEFAULT_RUNNING_THRESHOLD = 8.0      # Watts
DEFAULT_START_DELAY = 5              # minutes
DEFAULT_FINISH_DELAY = 2             # minutes
DEFAULT_DEBOUNCE_TIME = 20           # seconds

# Number entity limits
MIN_STANDBY_THRESHOLD = 0.0
MAX_STANDBY_THRESHOLD = 50.0
MIN_RUNNING_THRESHOLD = 1.0
MAX_RUNNING_THRESHOLD = 500.0
MIN_START_DELAY = 1
MAX_START_DELAY = 30
MIN_FINISH_DELAY = 1
MAX_FINISH_DELAY = 15
MIN_DEBOUNCE_TIME = 5
MAX_DEBOUNCE_TIME = 120

# State machine states
STATE_OFF = "off"
STATE_STANDBY = "standby"
STATE_PENDING_RUNNING = "pending_running"
STATE_RUNNING = "running"
STATE_PENDING_COMPLETED = "pending_completed"
STATE_COMPLETED = "completed"

# Events
EVENT_APPLIANCE_COMPLETED = "appliance_status_completed"

# Platform keys
PLATFORMS = ["sensor", "binary_sensor", "number"]
