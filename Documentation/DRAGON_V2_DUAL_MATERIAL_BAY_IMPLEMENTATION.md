# Dragon 400 V2 - Dual Material Bay Implementation Plan

## Overview

This document provides a complete implementation plan for adding dual material bay support to the Dragon 400 V2 printer. This configuration uses two redundant extruder motors (material bays A and B) connected via a Y-splitter to a single nozzle.

### Key Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Material Bay A │     │  Material Bay B │
│  (extruder_side0)│     │  (extruder_side1)│
│  [35cm PTFE]    │     │  [35cm PTFE]    │
│  [Runout+Jam]   │     │  [Runout+Jam]   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │    ┌─────────────┐   │
         └────┤ Y-Splitter  ├───┘
              └──────┬──────┘
                     │
              [96cm PTFE]
                     │
              ┌──────┴──────┐
              │   Toolhead  │
              │  (extruder) │
              │   Nozzle    │
              └─────────────┘
```

### PTFE Lengths (Dragon 400 V2)
- **Upstream (to Y-splitter)**: 96cm (960mm)
- **Material Bay Branch**: 35cm (350mm) each
- **Total retraction distance**: 131cm (1310mm)

### Critical Design Principles

#### 1. Python UI Controls Workflow

**Python UI code controls the load/unload workflow**, NOT Klipper GCode macros:
- **Klipper provides**: Motor sync (`SYNC_EXTRUDER_MOTION`), sensor management (`SET_FILAMENT_SENSOR`)
- **Python controls**: Heating, step-by-step extrusion/retraction, validation, persistence

#### 2. Persistence Pattern (IMPORTANT)

All dual bay state must be persisted to survive Klipper restarts and power outages:

| Storage | File | Survives Restart | Use Case |
|---------|------|------------------|----------|
| `PRINTER_VARIABLES` macro | `PRINTER_*.cfg` | ❌ No (resets to defaults) | **Only** for initial config values |
| `save_variables` | `/home/pi/variables.cfg` | ✅ Yes | Runtime state (active_material_bay, has_dual_material_bay) |

**Pattern for Klipper macros:**
```properties
# ✅ CORRECT - Read from persisted variables
{% set saved_vars = printer.save_variables.variables %}
{% set active_bay = saved_vars.active_material_bay|default('A') %}

# ❌ WRONG - This resets on Klipper restart!
{% set printer_vars = printer["gcode_macro PRINTER_VARIABLES"] %}
{% set active_bay = printer_vars.active_material_bay|default('A') %}

# ✅ CORRECT - Persist changes with SAVE_VARIABLE
SAVE_VARIABLE VARIABLE=active_material_bay VALUE="'B'"

# ❌ WRONG - This is lost on restart!
SET_GCODE_VARIABLE MACRO=PRINTER_VARIABLES VARIABLE=active_material_bay VALUE="'B'"
```

**Startup Flow:**
1. `DUAL_BAY_STARTUP` (delayed_gcode) runs 2 seconds after boot
2. Copies `has_dual_material_bay` from `PRINTER_VARIABLES` (config file) to `variables.cfg`
3. Reads `active_material_bay` from `variables.cfg` (persisted)
4. Calls `SYNC_MATERIAL_BAY` to sync motors and sensors

---

## Phase 1: Qt UI File Changes

### 1.1 Update filamentManagementScreen.ui

**File**: `octoprint_ControlCenter/ui/filament_management_screen/filamentManagementScreen.ui`

Add these new UI elements for Material Bay B:

| Element Name | Type | Description |
|--------------|------|-------------|
| `changeTool0MaterialBayB` | QToolButton | Change filament button for Bay B |
| `tool0MaterialBayBFrame` | QFrame | Container frame for Bay B UI |
| `editTool0MaterialBayB` | QPushButton | Edit Bay B settings button |
| `tool0MaterialBayBStateColor` | QLabel | Status color indicator for Bay B |
| `tool0MaterialBayBStateLabel` | QLabel | Status text label for Bay B |
| `tool0MaterialBayBLabel` | QLabel | "Bay B" label |
| `materialBayActiveIndicatorA` | QLabel | Active indicator dot for Bay A |
| `materialBayActiveIndicatorB` | QLabel | Active indicator dot for Bay B |

### 1.2 Existing Filament Path Images (Reuse)

**Location**: `octoprint_ControlCenter/ui/resources/img/Filament Paths/`

These images already exist in `resource.qrc` and can be reused:

| Image File | Use For |
|------------|-------------|
| `leftLoaded.png` | Bay A loaded, Bay B empty |
| `rightLoaded.png` | Bay A empty, Bay B loaded |
| `noneLoaded.png` | Both bays empty |
| `singleLoaded.png` | Single bay printers (non-dual) |

### 1.3 Phase 1 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 1.1.1 | Add Bay B UI elements to filamentManagementScreen.ui | ✅ |

---

## Phase 2: Klipper Firmware Changes

### 2.1 Create PRINTER_DRAGON_400_V2.cfg

**File**: `octoprint_ControlCenter/firmware/PRINTER_DRAGON_400_V2.cfg`

```properties
########################################
# PRINTERS_DRAGON_400_V2.cfg
# Dragon 400 V2 with Dual Material Bay (Y-splitter)
########################################

[include CORE_GCODE_MACROS.cfg]
[include BASE_DRAGON.cfg]
[include DUAL_MATERIAL_BAY_MACROS.cfg]

# Filament Sensors - Material Bay A (T0)
[include T0_FILAMENT_RUNOUT_SENSOR.cfg]
[include T0_FILAMENT_JAM_SENSOR.cfg]

# Filament Sensors - Material Bay B
[include MATERIAL_BAY_B_FILAMENT_RUNOUT_SENSOR.cfg]

# Other Add Ons
[include MAG_DOOR.cfg]
[include ELECTRONICS_CHAMBER_COOLING.cfg]

# Toolhead Configuration
[include TOOLHEADS_TD-01_TOOLHEAD0.cfg]

########################################
# Redundant Extruder - Material Bay B (extruder_side1)
# Note: extruder_side0 inherited from BASE_DRAGON.cfg
########################################

[extruder_stepper extruder_side1]
extruder:                           # Not synced by default
step_pin: PD4
dir_pin: PD3
enable_pin: !PD6 
microsteps: 16
rotation_distance: 7.710

[tmc5160 extruder_stepper extruder_side1]
cs_pin: PD5
spi_software_mosi_pin: PG6
spi_software_miso_pin: PG7
spi_software_sclk_pin: PG8
hold_current: 0.40
run_current: 1.00
interpolate: False
sense_resistor: 0.075

########################################
# PRINTER_VARIABLES - Dragon 400 V2 Specific
########################################

[gcode_macro PRINTER_VARIABLES]
variable_offset_x: 0
variable_offset_y: 0
variable_offset_z: 0
variable_autopark: 1
variable_z_hop: 0.6
variable_movespeed: 300
variable_feedrate: 8000
variable_bed_x_min: 0
variable_bed_x_max: 430
variable_bed_y_min: 0
variable_bed_y_max: 400
variable_bed_z_min: 0
variable_bed_z_max: 418
variable_fan0: 'extruder_CF'
variable_tool0_pause_position_x: -20
variable_tool0_pause_position_y: -20
# CRITICAL: Dual Material Bay Configuration
variable_is_dual_nozzle: 0
variable_has_dual_material_bay: 1
variable_active_material_bay: 'A'
variable_ptfe_tube_length: 960
variable_ptfe_bay_branch_length: 350
variable_ptfe_total_retract: 1310
# Bed Calibration Positions
variable_bed_calibration_x1: 25
variable_bed_calibration_y1: 75
variable_bed_calibration_x2: 375
variable_bed_calibration_y2: 75
variable_bed_calibration_x3: 200
variable_bed_calibration_y3: 280
variable_bed_calibration_x4: 224
variable_bed_calibration_y4: 236
gcode:
    G90

########################################
# Printer Kinematics
########################################

[printer]
kinematics: fracktal_hybrid_corexy
max_velocity: 600
max_accel: 6500
minimum_cruise_ratio: 0
square_corner_velocity: 100
max_z_velocity: 20
max_z_accel: 100

[stepper_x]
position_endstop: -21
position_min: -21
position_max: 430

[stepper_y]
position_endstop: 420
position_max: 420
position_min: -45

[stepper_z]
position_endstop: 417
position_max: 417
position_min: -6

[bed_mesh]
mesh_min: 25, 50
mesh_max: 400, 380
probe_count: 5,5
speed: 200

########################################
# Material Bay B Jam Sensor (Inline)
########################################

[filament_motion_sensor motion_sensor_bay_b]
switch_pin: ^PA0
detection_length: 15.0
extruder: extruder
pause_on_runout: False
runout_gcode:
    {% set printer_vars = printer["gcode_macro PRINTER_VARIABLES"] %}
    {% if printer.toolhead.homed_axes == "xyz" and printer_vars.active_material_bay|default('A') == 'B' %}
        RESPOND TYPE=echo MSG="Filament Jam detected on Material Bay B"
        PAUSE
    {% endif %}
insert_gcode:
    RESPOND TYPE=echo MSG="Filament motion restored on Material Bay B"

[delayed_gcode SET_BAY_B_JAM_SENSOR_STARTUP]
initial_duration: 1
gcode:
    SET_FILAMENT_SENSOR SENSOR=motion_sensor_bay_b ENABLE=0
```

### 2.2 Create DUAL_MATERIAL_BAY_MACROS.cfg

**File**: `octoprint_ControlCenter/firmware/DUAL_MATERIAL_BAY_MACROS.cfg`

> **IMPORTANT: Persistence Pattern**
> 
> All macros read/write from `printer.save_variables.variables` (persisted to `/home/pi/variables.cfg`)
> instead of `printer["gcode_macro PRINTER_VARIABLES"]` (runtime only, lost on restart).
>
> - **PRINTER_VARIABLES**: Defined in config file, used only on startup to initialize variables.cfg
> - **save_variables**: Persisted file, used by all runtime macros for active_material_bay and has_dual_material_bay

```properties
########################################
# DUAL_MATERIAL_BAY_MACROS.cfg
# Low-level macros for motor sync and sensor control
# All state reads from printer.save_variables.variables (persisted)
########################################

[gcode_macro SYNC_MATERIAL_BAY]
description: Sync a specific material bay extruder motor to the toolhead
gcode:
    {% set bay = params.BAY|default('A')|upper %}
    {% set saved_vars = printer.save_variables.variables %}
    
    {% if saved_vars.has_dual_material_bay|default(0) != 1 %}
        RESPOND TYPE=error MSG="Dual material bay not configured"
    {% else %}
        {% if bay == 'A' %}
            SYNC_EXTRUDER_MOTION EXTRUDER=extruder_side1 MOTION_QUEUE=
            SYNC_EXTRUDER_MOTION EXTRUDER=extruder_side0 MOTION_QUEUE=extruder
            SAVE_VARIABLE VARIABLE=active_material_bay VALUE="'A'"
            _SET_BAY_SENSORS BAY=A
            RESPOND TYPE=echo MSG="Material Bay A activated"
        {% elif bay == 'B' %}
            SYNC_EXTRUDER_MOTION EXTRUDER=extruder_side0 MOTION_QUEUE=
            SYNC_EXTRUDER_MOTION EXTRUDER=extruder_side1 MOTION_QUEUE=extruder
            SAVE_VARIABLE VARIABLE=active_material_bay VALUE="'B'"
            _SET_BAY_SENSORS BAY=B
            RESPOND TYPE=echo MSG="Material Bay B activated"
        {% else %}
            RESPOND TYPE=error MSG="Invalid bay '{bay}'. Use 'A' or 'B'"
        {% endif %}
    {% endif %}

[gcode_macro _SET_BAY_SENSORS]
description: Enable/disable sensors based on active bay (manual use only)
gcode:
    {% set bay = params.BAY|default('A')|upper %}
    RESPOND TYPE=echo MSG="_SET_BAY_SENSORS: Bay {bay} - sensor control handled by Python"

[gcode_macro GET_ACTIVE_MATERIAL_BAY]
description: Report which material bay is currently active
gcode:
    {% set saved_vars = printer.save_variables.variables %}
    {% if saved_vars.has_dual_material_bay|default(0) == 1 %}
        RESPOND TYPE=echo MSG="Active Material Bay: {saved_vars.active_material_bay|default('A')}"
    {% else %}
        RESPOND TYPE=echo MSG="Single material bay configuration"
    {% endif %}

[gcode_macro SAVE_ACTIVE_BAY]
description: Save current active bay to persistent storage
gcode:
    {% set saved_vars = printer.save_variables.variables %}
    {% set current_bay = saved_vars.active_material_bay|default('A') %}
    SAVE_VARIABLE VARIABLE=active_material_bay VALUE="'{current_bay}'"
    RESPOND TYPE=echo MSG="Saved active material bay: {current_bay}"

[delayed_gcode DUAL_BAY_STARTUP]
initial_duration: 2
gcode:
    ; Copy has_dual_material_bay from PRINTER_VARIABLES (config file) to variables.cfg
    {% set printer_vars = printer["gcode_macro PRINTER_VARIABLES"] %}
    {% set saved_vars = printer.save_variables.variables %}
    {% set config_has_dual = printer_vars.has_dual_material_bay|default(0) %}
    {% if config_has_dual == 1 %}
        SAVE_VARIABLE VARIABLE=has_dual_material_bay VALUE=1
        {% set saved_bay = saved_vars.active_material_bay|default('A') %}
        SYNC_MATERIAL_BAY BAY={saved_bay}
        RESPOND TYPE=echo MSG="Dual Material Bay initialized - Bay {saved_bay} active"
    {% else %}
        SAVE_VARIABLE VARIABLE=has_dual_material_bay VALUE=0
    {% endif %}
```

### 2.3 Bay B Sensors in PRINTER_DRAGON_400_V2.cfg

**Note**: Bay B sensors are now defined inline in PRINTER_DRAGON_400_V2.cfg and read from `printer.save_variables.variables`:

```properties
[filament_switch_sensor switch_sensor_bay_b]
switch_pin: ^PF0
pause_on_runout: False
runout_gcode:
    {% set saved_vars = printer.save_variables.variables %}
    {% if printer.toolhead.homed_axes == "xyz" and saved_vars.active_material_bay|default('A') == 'B' %}
        ; Use T0 format so Python handler can parse it - Bay B feeds tool0
        RESPOND TYPE=echo MSG="Filament Runout Detected on T0"
    {% endif %}
insert_gcode:
    RESPOND TYPE=echo MSG="Filament Inserted in Material Bay B"

[filament_motion_sensor encoder_sensor_bay_b]
switch_pin: ^PC15
detection_length: 12
extruder: extruder
pause_on_runout: False
runout_gcode:
    {% set saved_vars = printer.save_variables.variables %}
    {% if printer.toolhead.homed_axes == "xyz" and saved_vars.active_material_bay|default('A') == 'B' %}
        ; Use T0 format so Python handler can parse it - Bay B feeds tool0
        RESPOND TYPE=echo MSG="Filament Jam Detected on T0"
    {% endif %}
```

### 2.4 Phase 2 Checklist

| Task | Description | Status |
|------|-------------|--------|
| 2.1.1 | Create PRINTER_DRAGON_400_V2.cfg (includes Bay B sensors inline) | ✅ |
| 2.2.1 | Create DUAL_MATERIAL_BAY_MACROS.cfg | ✅ |

---

## Phase 3: Python Code Changes

### 3.1 Update config.py

**File**: `octoprint_ControlCenter/config.py`

**Changes Required**:

```python
# Add after existing defaults (around line 60)
DEFAULT_HAS_DUAL_MATERIAL_BAY = False
DEFAULT_PTFE_BAY_BRANCH_LENGTH = 350
DEFAULT_PTFE_TOTAL_RETRACT = 1310

# Add after existing runtime variables (around line 65)
HAS_DUAL_MATERIAL_BAY = DEFAULT_HAS_DUAL_MATERIAL_BAY
PTFE_BAY_BRANCH_LENGTH = DEFAULT_PTFE_BAY_BRANCH_LENGTH
PTFE_TOTAL_RETRACT = DEFAULT_PTFE_TOTAL_RETRACT

# Debug flag for testing without hardware
DEBUG_FORCE_DUAL_MATERIAL_BAY = False
```

**Update `load_printer_config_from_klipper()` function** (add to the global declarations and loading logic):

```python
def load_printer_config_from_klipper():
    try:
        from utils.printer_config_manager import get_printer_config_from_klipper
        
        config = get_printer_config_from_klipper()
        if not config:
            return False
            
        global calibrationPosition, machineBuildSize, tool0PurgePosition
        global tool1PurgePosition, ptfeTubeLength, IS_DUAL_NOZZLE
        global HAS_DUAL_MATERIAL_BAY, PTFE_BAY_BRANCH_LENGTH, PTFE_TOTAL_RETRACT  # ADD THIS
        
        # ... existing loading code ...
        
        # ADD: Load dual material bay configuration
        if 'hasDualMaterialBay' in config:
            HAS_DUAL_MATERIAL_BAY = config['hasDualMaterialBay']
        if 'ptfeBayBranchLength' in config:
            PTFE_BAY_BRANCH_LENGTH = config['ptfeBayBranchLength']
        if 'ptfeTotalRetract' in config:
            PTFE_TOTAL_RETRACT = config['ptfeTotalRetract']
        
        # Allow debug override
        if DEBUG_FORCE_DUAL_MATERIAL_BAY:
            HAS_DUAL_MATERIAL_BAY = True
            
        return True
    except Exception as e:
        return False
```

**Update `get_current_config()` function** (add new variables to returned dict):

```python
def get_current_config():
    return {
        # ... existing keys ...
        'HAS_DUAL_MATERIAL_BAY': HAS_DUAL_MATERIAL_BAY,
        'PTFE_BAY_BRANCH_LENGTH': PTFE_BAY_BRANCH_LENGTH,
        'PTFE_TOTAL_RETRACT': PTFE_TOTAL_RETRACT,
    }
```

### 3.2 Update printer_config_manager.py

**File**: `octoprint_ControlCenter/utils/printer_config_manager.py`

**Update `extract_printer_configuration()` method** (around line 300-360):

```python
def extract_printer_configuration(self, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Extract configuration from PRINTER_VARIABLES."""
    if not variables:
        return {}
        
    config = {
        # ... existing extraction code ...
        
        # ADD: Dual Material Bay configuration
        'hasDualMaterialBay': bool(variables.get('has_dual_material_bay', 0)),
        'activeMaterialBay': variables.get('active_material_bay', 'A'),
        'ptfeBayBranchLength': variables.get('ptfe_bay_branch_length', 350),
        'ptfeTotalRetract': variables.get('ptfe_total_retract', 1310),
    }
    
    return config
```

### 3.3 Update printer_preference_store.py

**File**: `octoprint_ControlCenter/utils/printer_preference_store.py`

**Update `DEFAULT_STATE`** (around line 17):

```python
DEFAULT_STATE = {
    "version": 2,  # Increment version for schema change
    "tools": {
        "tool0": {
            "material_bay_a": {"filament": None, "status": "Unknown", "nozzle": "Unknown"},
            "material_bay_b": {"filament": None, "status": "Unknown", "nozzle": "Unknown"}  # NEW
        },
        "tool1": {
            "material_bay_x": {"filament": None, "status": "Unknown", "nozzle": "Unknown"}
        },
    },
    "active_material_bay": "A",  # NEW
    "preferences": {
        "filament_runout_enabled": True,
        "filament_jam_enabled": True,
        "print_compatibility_check_enabled": True,
        "print_restore_enabled": True,
        "auto_resume_enabled": False,
        "firmware_update_check_enabled": True,
        "advanced_debugging_enabled": False,
    }
}
```

**Add new methods** (after existing methods, around line 230):

```python
def get_active_material_bay(self) -> str:
    """Get the currently active material bay (A or B) for dual bay printers."""
    return self.load_full().get("active_material_bay", "A")

def set_active_material_bay(self, bay: str) -> None:
    """Set the active material bay (A or B)."""
    with self._lock:
        data = self.load_full()
        if data.get("active_material_bay") != bay:
            data["active_material_bay"] = bay
            self._dirty = True
            if self._batch_depth == 0:
                self.save()
```

### 3.4 Update printer_model.py

**File**: `octoprint_ControlCenter/models/printer_model.py`

**Update `__init__` method** - Add new properties (around line 86):

```python
def __init__(self):
    super(PrinterModel, self).__init__()
    # ... existing init code ...
    
    # ADD: Dual Material Bay properties
    self.has_dual_material_bay = False
    self.ptfe_bay_branch_length = 350
    self.ptfe_total_retract = 1310
```

**Update initial `tools` dict** (around line 91):

```python
self.tools = {
    "tool0": {
        "material_bay_a": {"filament": None, "status": "Unknown", "nozzle": "Unknown"},
        "material_bay_b": {"filament": None, "status": "Unknown", "nozzle": "Unknown"}  # NEW
    },
    "tool1": {
        "material_bay_x": {"filament": None, "status": "Unknown", "nozzle": "Unknown"}
    },
}
```

**Update `_load_printer_configuration()` method** (around line 520):

```python
def _load_printer_configuration(self):
    """Load printer configuration from Klipper PRINTER_VARIABLES."""
    try:
        success = config.load_printer_config_from_klipper()
        
        if success:
            # ... existing property updates ...
            
            # ADD: Dual Material Bay properties
            self.has_dual_material_bay = config.HAS_DUAL_MATERIAL_BAY
            self.ptfe_bay_branch_length = config.PTFE_BAY_BRANCH_LENGTH
            self.ptfe_total_retract = config.PTFE_TOTAL_RETRACT
            
            self.logger.info("Successfully loaded printer configuration from Klipper")
            self.printer_config_updated.emit(self.get_printer_configuration())
        else:
            self.logger.warning("Failed to load printer configuration, using defaults")
    except Exception as e:
        self.logger.error(f"Error loading printer configuration: {e}")
```

**Add new method** (after `get_default_bay`, around line 500):

```python
def get_all_bays_for_tool(self, tool: str) -> list:
    """Get all available bays for a tool based on printer config."""
    if tool == "tool0" and self.has_dual_material_bay:
        return ["material_bay_a", "material_bay_b"]
    elif tool == "tool0":
        return ["material_bay_a"]
    elif tool == "tool1":
        return ["material_bay_x"]
    return []
```

**Update `get_printer_configuration()` method** (around line 560):

```python
def get_printer_configuration(self) -> dict:
    """Get current printer configuration as a dictionary."""
    return {
        'calibrationPosition': self.calibrationPosition,
        'machineBuildSize': self.machineBuildSize,
        'tool0PurgePosition': self.tool0PurgePosition,
        'tool1PurgePosition': self.tool1PurgePosition,
        'ptfeTubeLength': self.ptfeTubeLength,
        'IS_DUAL_NOZZLE': self.IS_DUAL_NOZZLE,
        # ADD:
        'has_dual_material_bay': self.has_dual_material_bay,
        'ptfe_bay_branch_length': self.ptfe_bay_branch_length,
        'ptfe_total_retract': self.ptfe_total_retract,
    }
```

### 3.5 Update printer_ui_config.py

**File**: `octoprint_ControlCenter/utils/printer_ui_config.py`

**Add after existing imports** (around line 10):

```python
def is_dual_material_bay_printer():
    """Check if the printer has dual material bay configuration."""
    return config.HAS_DUAL_MATERIAL_BAY
```

**Add new element list** (after `DUAL_NOZZLE_ELEMENTS`, around line 35):

```python
# Elements to show ONLY for dual material bay printers (hidden for single bay)
DUAL_MATERIAL_BAY_ONLY_ELEMENTS = {
    'filament_management_screen': [
        'changeTool0MaterialBayB', 'tool0MaterialBayBFrame', 'editTool0MaterialBayB',
        'tool0MaterialBayBStateColor', 'tool0MaterialBayBStateLabel',
        'tool0MaterialBayBLabel', 'materialBayActiveIndicatorA', 'materialBayActiveIndicatorB'
    ]
}
```

**Add new functions** (after existing functions, around line 90):

```python
def hide_dual_material_bay_elements(widget, element_names):
    """Hide dual material bay elements for single bay printers."""
    if not is_dual_material_bay_printer():
        for element_name in element_names:
            element = getattr(widget, element_name, None)
            if element:
                try:
                    element.hide()
                    logger.debug(f"Hidden dual material bay element: {element_name}")
                except Exception as e:
                    logger.error(f"Error hiding element {element_name}: {e}")

def get_dual_material_bay_elements(screen_name):
    """Get the list of dual material bay elements for a specific screen."""
    return DUAL_MATERIAL_BAY_ONLY_ELEMENTS.get(screen_name, [])

def apply_material_bay_config_to_screen(widget, screen_name):
    """Apply material bay configuration to a specific screen widget."""
    hide_dual_material_bay_elements(widget, get_dual_material_bay_elements(screen_name))
```

### 3.6 Update filamentManagementScreen.py

**File**: `octoprint_ControlCenter/ui/filament_management_screen/filamentManagementScreen.py`

**Add import** (at top of file):

```python
from utils.printer_ui_config import apply_nozzle_config_to_screen, apply_material_bay_config_to_screen, is_dual_material_bay_printer
from PyQt5.QtGui import QPixmap
```

**Add new UI element bindings in `__init__`** (after existing findChild calls, around line 60):

```python
# Material Bay B elements (dual material bay printers only)
self.changeTool0MaterialBayB = self.findChild(QToolButton, "changeTool0MaterialBayB")
self.tool0MaterialBayBLabel = self.findChild(QLabel, "tool0MaterialBayBLabel")
self.tool0MaterialBayBStateLabel = self.findChild(QLabel, "tool0MaterialBayBStateLabel")
self.tool0MaterialBayBStateColor = self.findChild(QLabel, "tool0MaterialBayBStateColor")
self.editTool0MaterialBayB = self.findChild(QPushButton, "editTool0MaterialBayB")
self.materialBayActiveIndicatorA = self.findChild(QLabel, "materialBayActiveIndicatorA")
self.materialBayActiveIndicatorB = self.findChild(QLabel, "materialBayActiveIndicatorB")

# Store reference to preference store for active bay tracking
self.preference_store = self.main_window.printer_model._config_store
self.model = self.main_window.printer_model
```

**Update button connections** (replace existing Bay A connection, around line 90):

```python
# Bay A button - now includes bay parameter
self.changeTool0MaterialBayA.clicked.connect(
    lambda: self.show_material_nozzle_screen(
        target_screen="filament_change", 
        params={"tool": "tool0", "bay": "A"}
    )
)

# Bay B button (dual material bay only)
if self.changeTool0MaterialBayB:
    self.changeTool0MaterialBayB.clicked.connect(
        lambda: self.show_material_nozzle_screen(
            target_screen="filament_change", 
            params={"tool": "tool0", "bay": "B"}
        )
    )

# Edit button for Bay B
if self.editTool0MaterialBayB:
    self.editTool0MaterialBayB.clicked.connect(
        lambda: self._open_edit_dialog("tool0", "material_bay_b")
    )
```

**Add call to apply_material_bay_configuration in `__init__`** (after apply_nozzle_configuration):

```python
self.apply_nozzle_configuration()
self.apply_material_bay_configuration()  # ADD THIS
```

**Replace `_apply_tool_ui` method** (around line 265):

```python
def _apply_tool_ui(self, tool: str, bay: str, data: dict):
    """Apply UI state for a specific tool and bay."""
    filament = data.get("filament") or "Unknown"
    status = data.get("status", "Unknown")
    display_filament = "-" if status == "Empty" else str(filament)
    nozzle = data.get("nozzle", "Unknown")
    
    if tool == "tool0" and bay == "material_bay_a":
        if self.changeTool0MaterialBayA:
            self.changeTool0MaterialBayA.setText(display_filament)
        if self.tool0MaterialBayAStateLabel:
            self.tool0MaterialBayAStateLabel.setText(str(status))
        if self.tool0MaterialBayAStateColor:
            self.tool0MaterialBayAStateColor.setStyleSheet(self._status_to_style(status))
        if self.changeTool0Button:
            self.changeTool0Button.setText("Unknown" if nozzle == "Unknown" or not nozzle else f"{nozzle} mm")
    elif tool == "tool0" and bay == "material_bay_b":
        if self.changeTool0MaterialBayB:
            self.changeTool0MaterialBayB.setText(display_filament)
        if self.tool0MaterialBayBStateLabel:
            self.tool0MaterialBayBStateLabel.setText(str(status))
        if self.tool0MaterialBayBStateColor:
            self.tool0MaterialBayBStateColor.setStyleSheet(self._status_to_style(status))
    elif tool == "tool1" and bay == "material_bay_x":
        if self.changeTool1MaterialBayX:
            self.changeTool1MaterialBayX.setText(display_filament)
        if self.tool1MaterialBayXStateLabel:
            self.tool1MaterialBayXStateLabel.setText(str(status))
        if self.tool11MaterialBayXStateColor:
            self.tool11MaterialBayXStateColor.setStyleSheet(self._status_to_style(status))
        if self.changeTool1Button:
            self.changeTool1Button.setText("Unknown" if nozzle == "Unknown" or not nozzle else f"{nozzle} mm")
    
    # Update filament path image for tool0
    if tool == "tool0":
        self.update_filament_path_image()
```

**Replace `_on_tool_states_loaded` method** (around line 293):

```python
def _on_tool_states_loaded(self, states: dict):
    """Handle initial tool state loading."""
    m = self.main_window.printer_model
    
    # Load Bay A state
    t0_a = m.get_bay_state("tool0", "material_bay_a")
    self._apply_tool_ui("tool0", "material_bay_a", t0_a)
    
    # Load Bay B state (dual material bay only)
    if config.HAS_DUAL_MATERIAL_BAY:
        t0_b = m.get_bay_state("tool0", "material_bay_b")
        self._apply_tool_ui("tool0", "material_bay_b", t0_b)
        self.refresh_dual_bay_ui()
    
    # Load Tool 1 state
    t1 = m.get_bay_state("tool1", "material_bay_x")
    self._apply_tool_ui("tool1", "material_bay_x", t1)
```

**Replace `_on_tool_state_changed` method** (around line 300):

```python
def _on_tool_state_changed(self, tool: str, bay: str, data: dict):
    """Handle tool state change signals."""
    if tool == "tool0":
        if bay == "material_bay_a":
            self._apply_tool_ui(tool, "material_bay_a", data)
        elif bay == "material_bay_b" and config.HAS_DUAL_MATERIAL_BAY:
            self._apply_tool_ui(tool, "material_bay_b", data)
    elif tool == "tool1" and bay == "material_bay_x":
        self._apply_tool_ui(tool, "material_bay_x", data)
```

**Update `_open_edit_dialog` method signature** (around line 307):

```python
def _open_edit_dialog(self, tool: str, bay: str = None):
    """Open edit dialog for a specific tool and bay."""
    model = self.main_window.printer_model
    bay = bay or model.get_default_bay(tool)  # Use provided bay or default
    current = model.get_bay_state(tool, bay)
    # ... rest of existing code, but use 'bay' variable instead of calling get_default_bay again
```

**Add new methods** (after `apply_nozzle_configuration`, around line 145):

```python
def apply_material_bay_configuration(self):
    """Hide dual material bay elements for single bay configuration."""
    apply_material_bay_config_to_screen(self, 'filament_management_screen')

def update_active_bay_indicator(self, active_bay: str):
    """Update visual indicators showing which bay is active."""
    if not config.HAS_DUAL_MATERIAL_BAY:
        return
    if hasattr(self, 'materialBayActiveIndicatorA') and self.materialBayActiveIndicatorA:
        if active_bay == 'A':
            self.materialBayActiveIndicatorA.setStyleSheet("background-color: #4CAF50; border-radius: 6px;")
        else:
            self.materialBayActiveIndicatorA.setStyleSheet("background-color: #757575; border-radius: 6px;")
    if hasattr(self, 'materialBayActiveIndicatorB') and self.materialBayActiveIndicatorB:
        if active_bay == 'B':
            self.materialBayActiveIndicatorB.setStyleSheet("background-color: #4CAF50; border-radius: 6px;")
        else:
            self.materialBayActiveIndicatorB.setStyleSheet("background-color: #757575; border-radius: 6px;")

def update_filament_path_image(self):
    """Update filament path image based on printer config and bay states."""
    if not hasattr(self, 'tool0FilamentTubeImage') or not self.tool0FilamentTubeImage:
        return
    
    if config.HAS_DUAL_MATERIAL_BAY:
        # Dual bay: show left/right/none based on which bay is loaded
        bay_a_state = self.model.get_bay_state("tool0", "material_bay_a")
        bay_b_state = self.model.get_bay_state("tool0", "material_bay_b")
        
        bay_a_loaded = bay_a_state.get("status") == "Loaded"
        bay_b_loaded = bay_b_state.get("status") == "Loaded"
        
        if bay_a_loaded:
            image_path = ":/img/Filament Paths/leftLoaded.png"
        elif bay_b_loaded:
            image_path = ":/img/Filament Paths/rightLoaded.png"
        else:
            image_path = ":/img/Filament Paths/noneLoaded.png"
    else:
        # Single bay: always show singleLoaded
        image_path = ":/img/Filament Paths/singleLoaded.png"
    
    self.tool0FilamentTubeImage.setPixmap(QPixmap(image_path))

def refresh_dual_bay_ui(self):
    """Refresh all dual material bay UI elements based on current state."""
    if config.HAS_DUAL_MATERIAL_BAY:
        active_bay = self.preference_store.get_active_material_bay()
        self.update_active_bay_indicator(active_bay)
    self.update_filament_path_image()
```

### 3.7 Update changeFilamentWizard.py

**File**: `octoprint_ControlCenter/ui/filament_management_screen/changeFilamentWizard/changeFilamentWizard.py`

**Add import** (at top of file):

```python
import config
```

**Update `__init__` method** (around line 80):

```python
def __init__(self, main_window):
    # ... existing init ...
    
    # ADD: Dual material bay tracking
    self.activeBay = 'A'
    self.hasDualMaterialBay = False
```

**Replace `setup` method** (around line 489):

```python
def setup(self, params=None):
    """Prepare and open the wizard for a specific tool and bay."""
    try:
        # Normalize params to a dict
        if isinstance(params, str):
            params = {'tool': params}
        elif params is None:
            params = {}
        elif not isinstance(params, dict):
            params = {}

        # Get tool
        tool = params.get('tool', 'tool0')
        tool = force_single_tool(tool)
        nozzle_index = int(tool.replace('tool', ''))
        self.setActiveExtruder(nozzle_index)
        
        # Handle dual material bay
        self.hasDualMaterialBay = config.HAS_DUAL_MATERIAL_BAY
        if self.hasDualMaterialBay and tool == 'tool0':
            self.activeBay = params.get('bay', 'A').upper()
            # Sync the material bay motor before starting
            self.octoprint_client.gcode(f"SYNC_MATERIAL_BAY BAY={self.activeBay}")
        else:
            self.activeBay = None
        
        self.changeFilament()
    except Exception as e:
        logger.error(f"Error in ChangeFilament.setup: {e}", exc_info=True)
        dialog.WarningOk(self, f"Error in ChangeFilament.setup: {e}", overlay=True)
```

**Add new helper methods** (after `calcExtrudeTime`, around line 460):

```python
def _get_extrusion_distance(self) -> int:
    """Get the total extrusion distance based on printer config."""
    if self.hasDualMaterialBay:
        return config.PTFE_TOTAL_RETRACT  # 1310mm
    return self.model.ptfeTubeLength

def _get_retraction_distance(self) -> int:
    """Get the total retraction distance based on printer config."""
    return self._get_extrusion_distance()

def _validate_bay_operation(self, is_load: bool) -> tuple:
    """Validate if the current bay operation is allowed.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not self.hasDualMaterialBay or not self.activeBay:
        return True, ""
    
    tool_key = "tool0"
    current_bay = f"material_bay_{self.activeBay.lower()}"
    other_bay = "material_bay_b" if self.activeBay == 'A' else "material_bay_a"
    
    current_state = self.model.get_bay_state(tool_key, current_bay)
    other_state = self.model.get_bay_state(tool_key, other_bay)
    
    if is_load:
        if current_state.get("status") == "Loaded":
            return False, f"Bay {self.activeBay} already has filament loaded. Please unload first."
        if other_state.get("status") == "Loaded":
            other_letter = 'B' if self.activeBay == 'A' else 'A'
            return False, f"Bay {other_letter} has filament loaded. Please unload Bay {other_letter} before loading into Bay {self.activeBay}."
        return True, ""
    else:
        if current_state.get("status") != "Loaded":
            return False, f"Bay {self.activeBay} has no filament to unload."
        return True, ""
```

**Replace `loadFilament` method** (around line 230):

```python
def loadFilament(self):
    """Begin Load flow with validation for dual material bay."""
    logger.info("changeFilament.loadFilament started")
    try:
        # Validate operation for dual material bay
        is_valid, error_msg = self._validate_bay_operation(is_load=True)
        if not is_valid:
            dialog.WarningOk(self, error_msg, overlay=True)
            return
        
        self._jog_to_purge_position()
        self.logger.debug("Jogging to purge position done")
        if self.changeFilamentComboBox.findText(LOADED_FILAMENT_LABEL) == -1:
            self._set_tool_temperature()
        self.stackedWidget.setCurrentWidget(self.changeFilamentProgressPage)
        self.model.temperatures_updated.connect(self.updateTemperature)
        self.changeFilamentStatus.setText(f"Heating Tool {self.activeExtruder}, Please Wait...")
        
        # Show bay info for dual material bay
        bay_info = f" (Bay {self.activeBay})" if self.hasDualMaterialBay and self.activeBay else ""
        self.changeFilamentNameOperation.setText(f"Loading {self.changeFilamentComboBox.currentText()}{bay_info}")
        
        self.changeFilamentHeatingFlag = True
        self.loadFlag = True
    except Exception as e:
        self.loadFlag = None
        self.changeFilamentHeatingFlag = False
        logger.error(f"Error in changeFilament.loadFilament: {e}")
        dialog.WarningOk(self, f"Error in changeFilament.loadFilament: {e}", overlay=True)
```

**Replace `unloadFilament` method** (around line 250):

```python
def unloadFilament(self):
    """Begin Unload flow with validation for dual material bay."""
    logger.info("changeFilament.unloadFilament started")
    try:
        # Validate operation for dual material bay
        is_valid, error_msg = self._validate_bay_operation(is_load=False)
        if not is_valid:
            dialog.WarningOk(self, error_msg, overlay=True)
            return
        
        self._jog_to_purge_position()
        if self.changeFilamentComboBox.findText(LOADED_FILAMENT_LABEL) == -1:
            self._set_tool_temperature()
        self.stackedWidget.setCurrentWidget(self.changeFilamentProgressPage)
        self.model.temperatures_updated.connect(self.updateTemperature)
        self.changeFilamentStatus.setText(f"Heating Tool {self.activeExtruder}, Please Wait...")
        
        # Show bay info for dual material bay
        bay_info = f" (Bay {self.activeBay})" if self.hasDualMaterialBay and self.activeBay else ""
        self.changeFilamentNameOperation.setText(f"Unloading {self.changeFilamentComboBox.currentText()}{bay_info}")
        
        self.changeFilamentHeatingFlag = True
        self.loadFlag = False
    except Exception as e:
        self.loadFlag = None
        self.changeFilamentHeatingFlag = False
        logger.error(f"Error in changeFilament.unloadFilament: {e}")
        dialog.WarningOk(self, f"Error in changeFilament.unloadFilament: {e}", overlay=True)
```

**Replace `changeFilamentExtrudePageFunction` method** (around line 395):

```python
@run_async
def changeFilamentExtrudePageFunction(self, *args, **kwargs):
    """After loading, extrude until filament reaches nozzle and purges reliably."""
    logger.info("ChangeFilament.changeFilamentExtrudePageFunction started")
    try:
        self.logger.debug("Entered extrusion loop to reach nozzle")
        self.stackedWidget.setCurrentWidget(self.changeFilamentExtrudePage)
        self._start_inactivity_timer()
        
        # Use appropriate distance for dual material bay or standard
        extrusion_distance = self._get_extrusion_distance()
        
        for i in range(int(extrusion_distance / 150)):
            self.octoprint_client.gcode("G91")
            self.octoprint_client.gcode("G1 E150 F1500")
            self.octoprint_client.gcode("G90")
            time.sleep(self.calcExtrudeTime(150, 1500))
            if self.stackedWidget.currentWidget() is not self.changeFilamentExtrudePage:
                self.logger.debug("Extrude page left; stopping initial extrusion steps")
                break
        
        self.logger.debug("Initial extrusion steps done; entering continuous purge loop")
        while self.stackedWidget.currentWidget() == self.changeFilamentExtrudePage:
            feed = 200 if self.changeFilamentComboBox.currentText() == TPU_MATERIAL_NAME else 400
            self.octoprint_client.gcode("G91")
            self.octoprint_client.gcode(f"G1 E20 F{feed}")
            self.octoprint_client.gcode("G90")
            time.sleep(self.calcExtrudeTime(20, feed))
        self.logger.debug("Extrude page loop exited")
    except Exception as e:
        logger.error(f"Error in ChangeFilament.changeFilamentExtrudePageFunction: {e}")
        dialog.WarningOk(self, f"Error in ChangeFilament.changeFilamentExtrudePageFunction: {e}", overlay=True)
    finally:
        self._stop_inactivity_timer()
```

**Replace `changeFilamentRetractFunction` method** (around line 425):

```python
@run_async
def changeFilamentRetractFunction(self):
    """After heating (Unload): tip-shape and retract filament through the tube."""
    logger.info("ChangeFilament.changeFilamentRetractFunction started")
    try:
        self.logger.debug("Entered retraction loop")
        self.stackedWidget.setCurrentWidget(self.changeFilamentRetractPage)
        self._start_inactivity_timer()
        
        # Tip shaping
        feed = 300 if self.changeFilamentComboBox.currentText() == TPU_MATERIAL_NAME else 600
        self.octoprint_client.gcode("G91")
        self.octoprint_client.gcode(f"G1 E10 F{feed}")
        time.sleep(self.calcExtrudeTime(10, feed))
        self.octoprint_client.gcode("G1 E-25 F6000")
        time.sleep(self.calcExtrudeTime(20, 6000))
        time.sleep(8)
        self.octoprint_client.gcode("G1 E-150 F5000")
        time.sleep(self.calcExtrudeTime(150, 5000))
        self.octoprint_client.gcode("G90")
        
        # Use appropriate distance for dual material bay or standard
        retraction_distance = self._get_retraction_distance()
        
        for _ in range(int(retraction_distance / 150)):
            self.octoprint_client.gcode("G91")
            self.octoprint_client.gcode("G1 E-150 F2000")
            self.octoprint_client.gcode("G90")
            time.sleep(self.calcExtrudeTime(150, 2000))
            if self.stackedWidget.currentWidget() is not self.changeFilamentRetractPage:
                self.logger.debug("Retract page left; stopping tube retraction steps")
                break
        
        while self.stackedWidget.currentWidget() == self.changeFilamentRetractPage:
            self.octoprint_client.gcode("G91")
            self.octoprint_client.gcode("G1 E-5 F1000")
            self.octoprint_client.gcode("G90")
            time.sleep(self.calcExtrudeTime(5, 1000))
        self.logger.debug("Retract page loop exited")
    except Exception as e:
        logger.error(f"Error in ChangeFilament.changeFilamentRetractFunction: {e}")
        dialog.WarningOk(self, f"Error in ChangeFilament.changeFilamentRetractFunction: {e}", overlay=True)
    finally:
        self._stop_inactivity_timer()
```

**Replace `changeFilamentDone` method** (around line 520):

```python
def changeFilamentDone(self):
    """Finalize the operation, persist tool state, and return to main screen."""
    logger.info("ChangeFilament.changeFilamentDone started")
    try:
        self._stop_inactivity_timer()
        
        if self.loadFlag is not None:
            try:
                tool_key = f"tool{int(self.activeExtruder)}"
                
                # Determine correct bay for dual material bay printers
                if self.hasDualMaterialBay and self.activeBay:
                    bay = f"material_bay_{self.activeBay.lower()}"
                else:
                    bay = self.main_window.printer_model.get_default_bay(tool_key)
                
                # Determine selected filament name
                selected = None
                try:
                    selected_text = self.changeFilamentComboBox.currentText()
                    if selected_text and selected_text != "Loaded Filament":
                        selected = selected_text
                except Exception:
                    selected = None

                if bool(self.loadFlag):
                    self.model.update_tool_bay_state(tool_key, bay=bay, filament=selected, status="Loaded", persist=True)
                    if self.hasDualMaterialBay:
                        self.octoprint_client.gcode("SAVE_ACTIVE_BAY")
                else:
                    self.model.update_tool_bay_state(tool_key, bay=bay, filament=None, status="Empty", persist=True)
            except Exception as e:
                logger.warning(f"Failed to persist tool state on filament change done: {e}")

        self._disconnect_temperature_signal()
        self.stackedWidget.setCurrentWidget(self.changeFilamentPage)
        self.main_window.filament_management_screen.show_material_nozzle_screen()
        self.changeFilamentHeatingFlag = False
        self.loadFlag = None
    except Exception as e:
        logger.error(f"Error in ChangeFilament.changeFilamentDone: {e}")
        dialog.WarningOk(self, f"Error in ChangeFilament.changeFilamentDone: {e}", overlay=True)
```

### 3.8 Phase 3 Checklist

| Task | File | Description | Status |
|------|------|-------------|--------|
| 3.1.1 | config.py | Add HAS_DUAL_MATERIAL_BAY and related globals | ⬜ |
| 3.1.2 | config.py | Update load_printer_config_from_klipper() | ⬜ |
| 3.2.1 | printer_config_manager.py | Update extract_printer_configuration() | ⬜ |
| 3.3.1 | printer_preference_store.py | Update DEFAULT_STATE with bay_b | ⬜ |
| 3.3.2 | printer_preference_store.py | Add get/set_active_material_bay() | ⬜ |
| 3.4.1 | printer_model.py | Add has_dual_material_bay property | ⬜ |
| 3.4.2 | printer_model.py | Update initial tools dict with bay_b | ⬜ |
| 3.4.3 | printer_model.py | Add get_all_bays_for_tool() | ⬜ |
| 3.4.4 | printer_model.py | Update _load_printer_configuration() | ⬜ |
| 3.5.1 | printer_ui_config.py | Add is_dual_material_bay_printer() | ⬜ |
| 3.5.2 | printer_ui_config.py | Add DUAL_MATERIAL_BAY_ONLY_ELEMENTS | ⬜ |
| 3.5.3 | printer_ui_config.py | Add apply_material_bay_config_to_screen() | ⬜ |
| 3.6.1 | filamentManagementScreen.py | Add Bay B UI bindings | ⬜ |
| 3.6.2 | filamentManagementScreen.py | Update _apply_tool_ui() with bay param | ⬜ |
| 3.6.3 | filamentManagementScreen.py | Update _on_tool_state_changed() | ⬜ |
| 3.6.4 | filamentManagementScreen.py | Update _on_tool_states_loaded() | ⬜ |
| 3.6.5 | filamentManagementScreen.py | Add update_active_bay_indicator() | ⬜ |
| 3.6.6 | filamentManagementScreen.py | Add update_filament_path_image() | ⬜ |
| 3.6.7 | filamentManagementScreen.py | Update _open_edit_dialog() with bay param | ⬜ |
| 3.7.1 | changeFilamentWizard.py | Add activeBay/hasDualMaterialBay to init | ⬜ |
| 3.7.2 | changeFilamentWizard.py | Update setup() with bay handling | ⬜ |
| 3.7.3 | changeFilamentWizard.py | Add _get_extrusion_distance() | ⬜ |
| 3.7.4 | changeFilamentWizard.py | Add _validate_bay_operation() | ⬜ |
| 3.7.5 | changeFilamentWizard.py | Update loadFilament() with validation | ⬜ |
| 3.7.6 | changeFilamentWizard.py | Update unloadFilament() with validation | ⬜ |
| 3.7.7 | changeFilamentWizard.py | Update changeFilamentExtrudePageFunction() | ⬜ |
| 3.7.8 | changeFilamentWizard.py | Update changeFilamentRetractFunction() | ⬜ |
| 3.7.9 | changeFilamentWizard.py | Update changeFilamentDone() | ⬜ |

---

## Testing Plan

### Validation Rules for Dual Material Bay

1. **Cannot load if other bay is loaded** - Y-splitter means one path only
2. **Must unload before switching bays** - Prevents collision
3. **Bay sync happens before extrusion** - Correct motor must be active

### Test Cases

| Test | Expected Result |
|------|-----------------|
| Load Bay A (both empty) | ✅ Succeeds |
| Load Bay B (both empty) | ✅ Succeeds |
| Load Bay A (Bay B loaded) | ❌ Fails with error message |
| Load Bay B (Bay A loaded) | ❌ Fails with error message |
| Unload Bay A (Bay A loaded) | ✅ Succeeds |
| Unload Bay A (Bay A empty) | ❌ Fails with error message |
| Dragon 400 V1 config | Bay B UI hidden |
| TwinDragon config | Bay B UI hidden |
| Dragon 400 V2 config | Bay B UI visible |

---

## File Summary

### New Files

| File | Phase |
|------|-------|
| `firmware/PRINTER_DRAGON_400_V2.cfg` | 2 |
| `firmware/DUAL_MATERIAL_BAY_MACROS.cfg` | 2 |

### Existing Resources (Reuse)

| File | Use For |
|------|-------|
| `ui/resources/img/Filament Paths/leftLoaded.png` | Bay A loaded |
| `ui/resources/img/Filament Paths/rightLoaded.png` | Bay B loaded |
| `ui/resources/img/Filament Paths/noneLoaded.png` | Both empty |

### Modified Files

| File | Phase |
|------|-------|
| `ui/filament_management_screen/filamentManagementScreen.ui` | 1 |
| `config.py` | 3 |
| `utils/printer_config_manager.py` | 3 |
| `utils/printer_preference_store.py` | 3 |
| `utils/printer_ui_config.py` | 3 |
| `models/printer_model.py` | 3 |
| `ui/filament_management_screen/filamentManagementScreen.py` | 3 |
| `ui/filament_management_screen/changeFilamentWizard/changeFilamentWizard.py` | 3 |

---

## GCode Command Reference

| Command | Description |
|---------|-------------|
| `SYNC_MATERIAL_BAY BAY=<A\|B>` | Sync specified bay motor to toolhead |
| `GET_ACTIVE_MATERIAL_BAY` | Report active bay |
| `SAVE_ACTIVE_BAY` | Save active bay to persistent storage |

---

## Notes

### Hardware Pin Assignments
Sensor pins (PF0, PA0) are **placeholders** - verify against actual Dragon 400 V2 hardware.

### Debug Testing
Set `DEBUG_FORCE_DUAL_MATERIAL_BAY = True` in config.py to test UI without hardware.

### Backward Compatibility
All changes default to single-bay behavior when `has_dual_material_bay = 0`.

---

## Implementation Updates (January 2026)

This section documents changes made during actual implementation that differ from or extend the original plan.

### Firmware Changes

#### 2.1.1 PRINTER_DRAGON_400_V2.cfg - Axis Settings Alignment

The Dragon 400 V2 config now uses **identical axis and kinematics settings** as PRINTER_DRAGON_400.cfg. Only material bay-specific configurations differ:

```properties
# Axis settings (same as Dragon 400)
[stepper_x]
position_endstop: -40.000
position_min: -40.000
position_max: 420.000

[stepper_y]
position_endstop: 314
position_max: 314
position_min: -40

[stepper_z]
position_endstop: 418
position_max: 418
position_min: -6

[bed_mesh]
mesh_min: 25, 50
mesh_max: 375, 250
probe_count: 4,3
speed: 200
```

#### 2.1.2 Bay B Sensors - Inline Configuration

Material Bay B sensors are now **embedded directly** in `PRINTER_DRAGON_400_V2.cfg` instead of separate include files:

```properties
########################################
# Material Bay B Filament Sensors
# Reuses T1 sensor pins (^PF0 runout, ^PC15 jam)
########################################

[filament_switch_sensor switch_sensor_bay_b]
switch_pin: ^PF0
pause_on_runout: False
runout_gcode:
    {% set printer_vars = printer["gcode_macro PRINTER_VARIABLES"] %}
    {% if printer.toolhead.homed_axes == "xyz" and printer_vars.active_material_bay|default('A') == 'B' %}
        ; Use T0 format so Python handler can parse it - Bay B feeds tool0
        RESPOND TYPE=echo MSG="Filament Runout Detected on T0"
    {% endif %}
insert_gcode:
    RESPOND TYPE=echo MSG="Filament Inserted in Material Bay B"

[filament_motion_sensor encoder_sensor_bay_b]
switch_pin: ^PC15
detection_length: 12
extruder: extruder
pause_on_runout: False
runout_gcode:
    {% set printer_vars = printer["gcode_macro PRINTER_VARIABLES"] %}
    {% if printer.toolhead.homed_axes == "xyz" and printer_vars.active_material_bay|default('A') == 'B' %}
        ; Use T0 format so Python handler can parse it - Bay B feeds tool0
        RESPOND TYPE=echo MSG="Filament Jam Detected on T0"
    {% endif %}
```

**Key Decision**: Bay B sensor messages use `"on T0"` format instead of `"on Material Bay B"` because the Python handler parses for tool identifiers. Both bays feed tool0.

#### 2.1.3 printer.cfg Template Update

Added `PRINTER_DRAGON_400_V2.cfg` include line to the printer.cfg template:

```properties
#[include PRINTER_TWINDRAGON_300.cfg]
[include PRINTER_DRAGON_400.cfg]
#[include PRINTER_DRAGON_400_V2.cfg]   # <-- Added
#[include PRINTER_DRAGON_500.cfg]
```

### Python UI Changes

#### 3.6.8 Filament Path Image - Dynamic Sizing

Added `_configure_filament_path_image_size()` method to stretch the filament path image horizontally on dual material bay printers:

```python
def _configure_filament_path_image_size(self):
    """Configure filament path image size based on printer type."""
    if is_dual_material_bay_printer():
        # Stretch image for dual material bay - wider to span both bays
        self.tool0FilamentTubeImage.setMaximumSize(350, 60)
        self.tool0FilamentTubeImage.setMinimumWidth(300)
        self.tool0FilamentTubeImage.setStyleSheet("margin-left: 0px; margin-right: 0px;")
    else:
        # Single bay - keep original sizing
        self.tool0FilamentTubeImage.setMaximumSize(200, 60)
        self.tool0FilamentTubeImage.setStyleSheet("margin-left: 50px; margin-right: 50px;")
```

#### 3.6.9 Filament Path Image Updates

Added `update_filament_path_image()` method to dynamically update the image based on bay states:

| Printer Type | Bay A State | Bay B State | Image |
|--------------|-------------|-------------|-------|
| Dual Bay | Loaded | Empty/Unknown | `leftLoaded.png` |
| Dual Bay | Empty/Unknown | Loaded | `rightLoaded.png` |
| Dual Bay | Empty | Empty | `noneLoaded.png` |
| Single Bay | Any | N/A | `singleLoaded.png` |

#### 3.6.10 Active Bay Indicator Updates

Added `update_active_bay_indicators()` method and connected to new `active_material_bay_changed` signal:

```python
# Signal in printer_model.py
active_material_bay_changed = pyqtSignal(str)  # 'A' or 'B'

# In set_active_material_bay()
self.active_material_bay_changed.emit(bay.upper())

# Indicator styling
active_style = "background-color: #4CAF50; border-radius: 6px;"   # Green
inactive_style = "background-color: #757575; border-radius: 6px;" # Gray
```

#### 3.6.11 Nozzle Sync Across Bays

When editing Bay A or Bay B on a dual material bay printer, the nozzle size is automatically synced to the other bay (since both bays share the same physical nozzle):

```python
# In _open_edit_dialog(), after saving:
if is_dual_material_bay_printer() and tool == "tool0":
    other_bay = "material_bay_b" if bay == "material_bay_a" else "material_bay_a"
    other_state = model.get_bay_state(tool, other_bay)
    model.update_tool_bay_state(
        tool, 
        bay=other_bay, 
        filament=other_state.get("filament"),  # Keep filament unchanged
        status=other_state.get("status", "Unknown"),  # Keep status unchanged
        nozzle=nozzle,  # Sync nozzle size
        persist=True
    )
```

#### 3.6.12 Active Bay Selector in Edit Dialog

Added an "Active Bay" dropdown to the material bay edit dialog for dual material bay printers. This allows users to override/update the currently active material bay directly from the edit dialog:

```python
# Add active bay selector for dual material bay printers (tool0 only)
cb_active_bay = None
if is_dual_material_bay_printer() and tool == "tool0":
    cb_active_bay = QComboBox(dialog_widget)
    cb_active_bay.addItem("Bay A")
    cb_active_bay.addItem("Bay B")
    current_active = model.get_active_material_bay()
    cb_active_bay.setCurrentIndex(0 if current_active == 'A' else 1)
    
    lab_active_bay = QLabel("Active Bay", dialog_widget)
    form.addRow(lab_active_bay, cb_active_bay)

# On dialog accept, update active bay if changed:
if cb_active_bay:
    new_active_bay = 'A' if cb_active_bay.currentIndex() == 0 else 'B'
    current_active = model.get_active_material_bay()
    if new_active_bay != current_active:
        model.set_active_material_bay(new_active_bay)
        # Sync to Klipper - SYNC_MATERIAL_BAY persists to variables.cfg
        self.octoprint_client.gcode(f"SYNC_MATERIAL_BAY BAY={new_active_bay}")
```

**Edit Dialog Fields for Dual Material Bay (tool0):**

| Field | Description |
|-------|-------------|
| Filament | Filament type loaded in this bay |
| Status | Empty, Unknown, Loaded, Staged |
| Nozzle | Nozzle size (synced across both bays) |
| Active Bay | Which bay is currently active (A or B) |

### UI Element References Added

| Element | Description |
|---------|-------------|
| `tool0FilamentTubeImage` | QLabel for filament path visualization (tool0) |
| `tool1FilamentTubeImage` | QLabel for filament path visualization (tool1) |
| `materialBayActiveIndicatorA` | QLabel active indicator for Bay A |
| `materialBayActiveIndicatorB` | QLabel active indicator for Bay B |

### Updated Checklist Items

| Task | File | Description | Status |
|------|------|-------------|--------|
| 3.6.8 | filamentManagementScreen.py | Add _configure_filament_path_image_size() | ✅ |
| 3.6.9 | filamentManagementScreen.py | Add update_filament_path_image() | ✅ |
| 3.6.10 | filamentManagementScreen.py | Add update_active_bay_indicators() | ✅ |
| 3.6.11 | filamentManagementScreen.py | Add nozzle sync in _open_edit_dialog() | ✅ |
| 3.6.12 | filamentManagementScreen.py | Add active bay selector in _open_edit_dialog() | ✅ |
| 3.4.5 | printer_model.py | Add active_material_bay_changed signal | ✅ |
| 2.1.4 | printer.cfg | Add PRINTER_DRAGON_400_V2.cfg include | ✅ |
| 3.8.1 | home_screen.ui | Add activeMaterialBayLabel to title bar | ✅ |
| 3.8.2 | home_screen.py | Add apply_material_bay_configuration() | ✅ |
| 3.8.3 | home_screen.py | Add update_active_material_bay_display() | ✅ |

### Backward Compatibility Verified

All new functionality is gated by `is_dual_material_bay_printer()` checks:
- Returns `False` for Dragon 400, Dragon 500, TwinDragon models
- UI sizing, image updates, bay indicators, nozzle sync, and active bay selector only activate for Dragon 400 V2

---

### Home Screen Active Bay Display (January 2026)

Added active material bay label to the home screen title bar for dual material bay printers:

#### 3.8.1 home_screen.ui Changes

Added `activeMaterialBayLabel` QLabel in the status bar (centered between printer status and IP):

```xml
<widget class="QLabel" name="activeMaterialBayLabel">
  <property name="font">
    <font>
      <family>Montserrat</family>
      <pointsize>12</pointsize>
      <weight>75</weight>
      <bold>true</bold>
    </font>
  </property>
  <property name="styleSheet">
    <string notr="true">color: rgb(76, 175, 80);
background-color: rgba(76, 175, 80, 30);
padding: 2px 8px;
border-radius: 4px;</string>
  </property>
  <property name="text">
    <string>Bay A</string>
  </property>
</widget>
```

**Layout structure:**
```
[printerStatusColour] [printerStatus] [spacer] [activeMaterialBayLabel] [spacer] [ipStatus]
```

#### 3.8.2 home_screen.py Changes

Added methods to handle the active material bay label:

```python
def apply_material_bay_configuration(self):
    """Show/hide active material bay label based on printer configuration."""
    if self.activeMaterialBayLabel:
        if is_dual_material_bay_printer():
            self.activeMaterialBayLabel.show()
            active_bay = self.main_window.printer_model.get_active_material_bay()
            self.update_active_material_bay_display(active_bay)
        else:
            self.activeMaterialBayLabel.hide()

def update_active_material_bay_display(self, bay: str):
    """Update the active material bay label in the title bar."""
    if self.activeMaterialBayLabel and is_dual_material_bay_printer():
        self.activeMaterialBayLabel.setText(f"Bay {bay.upper()}")
```

**Signal connection:**
```python
self.main_window.printer_model.active_material_bay_changed.connect(self.update_active_material_bay_display)
```

#### Behavior

| Printer Type | Label Visibility | Display |
|--------------|------------------|---------|
| Dragon 400 V2 (dual bay) | Visible | "Bay A" or "Bay B" (green badge) |
| Dragon 400, 500, TwinDragon | Hidden | N/A |

The label automatically updates when the active bay changes via the `active_material_bay_changed` signal.
