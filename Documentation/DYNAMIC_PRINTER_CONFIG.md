# Dynamic Printer Configuration System

## Overview

This implementation creates a dynamic printer configuration system that extracts printer-specific settings from Klipper's `PRINTER_VARIABLES` macro instead of using hardcoded values in `config.py`. The system correctly follows Klipper's architecture where the main `printer.cfg` acts as a selector file that includes specific printer configurations, and the `PRINTER_VARIABLES` macro is defined in the individual `PRINTER_<NAME>.cfg` files.

## Architecture

### Configuration File Structure

```
/home/pi/                           # Klipper config directory
├── printer.cfg                    # Main selector file (no PRINTER_VARIABLES)
│   ├── [include PRINTER_DRAGON_400.cfg]     # Only one uncommented
│   ├── # [include PRINTER_DRAGON_500.cfg]   # Others commented out
│   └── # [include PRINTER_TWINDRAGON_600.cfg]
├── PRINTER_DRAGON_400.cfg         # Contains PRINTER_VARIABLES macro
├── PRINTER_DRAGON_500.cfg         # Contains PRINTER_VARIABLES macro
├── PRINTER_TWINDRAGON_600.cfg     # Contains PRINTER_VARIABLES macro
├── PRINTER_TWINDRAGON_600x300.cfg # Contains PRINTER_VARIABLES macro
└── [other config files...]
```

### PRINTER_VARIABLES Location

- **❌ NOT in `printer.cfg`** - The main printer.cfg is a selector file only
- **✅ IN `PRINTER_<NAME>.cfg`** - Each printer configuration contains its own PRINTER_VARIABLES macro
- **✅ Deployed to `/home/pi/`** - Files are deployed from firmware directory to Klipper config directory
- **🎯 READ FROM `/home/pi/`** - Parser reads from deployed location where Klipper actually reads from
- **🔄 FALLBACK to `firmware/`** - Falls back to firmware directory if deployed files not found

## Key Changes

### 1. Unified Printer Configuration Manager (`utils/printer_config_manager.py`)

**Purpose**: Unified utility for managing both Klipper and OctoPrint configuration files, printer selection, variable parsing, and backup operations.

**Key Functions**:
- `parse_printer_variables_from_file()` - Parses variables from a specific config file
- `get_printer_variables_from_active_config()` - Determines active printer and gets its variables
- `extract_printer_configuration()` - Converts raw variables to application configuration
- `get_printer_config_from_klipper()` - Main entry point for getting complete config
- `copy_firmware_files()` - Deploys firmware files and updates printer selection
- `update_octoprint_config()` - Updates OctoPrint configuration files
- `get_current_printer_selection()` - Gets currently active printer from printer.cfg

**Parser Logic**:
1. **Determine Active Printer**: Parse `printer.cfg` to find which `PRINTER_<NAME>.cfg` is active
2. **Look in Klipper Directory**: First try `/home/pi/PRINTER_<NAME>.cfg` (deployed location where Klipper reads from)
3. **Fallback to Firmware Directory**: If not found, try local `firmware/PRINTER_<NAME>.cfg`
4. **Extract Variables**: Parse the `PRINTER_VARIABLES` macro from the found configuration file
5. **Transform Configuration**: Convert raw variables to application-compatible format

**Extracted Configuration**:
- `machineBuildSize` - Calculated from `bed_x_min/max`, `bed_y_min/max`, `bed_z_min/max`
- `calibrationPosition` - From explicit `variable_bed_calibration_**` variables or calculated fallback
- `tool0PurgePosition` - From `tool0_pause_position_x/y`
- `tool1PurgePosition` - From `tool1_pause_position_x/y` (only for dual nozzle printers)
- `ptfeTubeLength` - From explicit `variable_ptfe_tube_length` or calculated based on machine X dimension
- `IS_DUAL_NOZZLE` - From explicit `variable_is_dual_nozzle` boolean value

### 2. Updated Configuration System (`config.py`)

**Changes**:
- Moved printer-specific configs to "Default/fallback" section with clear DEFAULT_ prefixes
- Added dynamic configuration variables that are updated at runtime
- Added `load_printer_config_from_klipper()` function that calls `PrinterConfigManager`
- Added `get_printer_config()` helper function to access current configuration
- **Clean Separation**: Configuration data only (no logic functions), all logic moved to `printer_config_manager.py`

**Fallback Strategy**: System uses default values if Klipper configuration cannot be read, ensuring robust operation.

**Current Configuration Variables**:
```python
# Default/fallback values (used when Klipper config unavailable)
DEFAULT_CALIBRATION_POSITION = {'X1': 110, 'Y1': 18, 'X2': 510, 'Y2': 18, 'X3': 310, 'Y3': 308, 'X4': 310, 'Y4': 178}
DEFAULT_MACHINE_BUILD_SIZE = {'X': 600, 'Y': 300, 'Z': 400}
DEFAULT_TOOL0_PURGE_POSITION = {'X': -30, 'Y': -77}
DEFAULT_TOOL1_PURGE_POSITION = {'X': 655, 'Y': -77}
DEFAULT_PTFE_TUBE_LENGTH = 1500
DEFAULT_IS_DUAL_NOZZLE = True

# Dynamic variables (updated from Klipper at runtime)
calibrationPosition = DEFAULT_CALIBRATION_POSITION.copy()
machineBuildSize = DEFAULT_MACHINE_BUILD_SIZE.copy()
tool0PurgePosition = DEFAULT_TOOL0_PURGE_POSITION.copy()
tool1PurgePosition = DEFAULT_TOOL1_PURGE_POSITION.copy()
ptfeTubeLength = DEFAULT_PTFE_TUBE_LENGTH
IS_DUAL_NOZZLE = DEFAULT_IS_DUAL_NOZZLE
```

### 3. Enhanced Printer Model (`models/printer_model.py`)

**New Features**:
- `_load_printer_configuration()` - Loads config from Klipper during initialization
- `reload_printer_configuration()` - Public method to refresh configuration
- `get_printer_configuration()` - Returns current configuration as dictionary
- `printer_config_updated` signal - Notifies when configuration changes

**Integration**: Configuration is automatically loaded during:
- Printer model initialization
- WebSocket connection establishment (via main controller)
- Printer type changes (via printer setup)

**Configuration Properties**: All printer-specific properties are dynamically updated from Klipper:
```python
self.calibrationPosition = config.calibrationPosition
self.tool0PurgePosition = config.tool0PurgePosition  
self.tool1PurgePosition = config.tool1PurgePosition
self.ptfeTubeLength = config.ptfeTubeLength
self.machineBuildSize = config.machineBuildSize
self.IS_DUAL_NOZZLE = config.IS_DUAL_NOZZLE
```

### 4. Updated Main Controller (`controller/main_controller.py`)

**Enhancement**: Uses `PrinterConfigManager` for printer.cfg validation and backup management.

**Key Functions**:
- `checkKlipperPrinterCFG()` - Validates printer configuration and handles backup/restore operations

### 5. Updated Printer Setup (`ui/settings_screen/printer_setup/`)

**Enhancement**: Uses enhanced `PrinterConfigManager` for complete printer setup workflow:

**Features**:
- **Dynamic Configuration Extraction**: All printer settings read from `PRINTER_VARIABLES` in firmware files
- **No Hardcoded Settings**: Printer specifications extracted in real-time from firmware files  
- **Scalable Architecture**: New printers added by placing firmware file in firmware folder
- **Klipper Configuration**: Copies all firmware files and updates printer.cfg with selected printer
- **OctoPrint Configuration**: Updates both `config.yaml` and `_default.profile` with printer-specific settings

## Configuration Mapping

### PRINTER_VARIABLES Structure

Each `PRINTER_<NAME>.cfg` file contains a `PRINTER_VARIABLES` macro with printer-specific settings:

```gcode
[gcode_macro PRINTER_VARIABLES]
# Printer Configuration
variable_is_dual_nozzle: 0  # 0 for single nozzle, 1 for dual nozzle
variable_ptfe_tube_length: 1500  # PTFE tube length in mm

# Bed Calibration Positions (explicit coordinates)
variable_bed_calibration_x1: 77
variable_bed_calibration_y1: 24
variable_bed_calibration_x2: 365
variable_bed_calibration_y2: 24
variable_bed_calibration_x3: 224
variable_bed_calibration_y3: 376
variable_bed_calibration_x4: 224
variable_bed_calibration_y4: 236

# HeatBed size
variable_bed_x_min: 0
variable_bed_x_max: 430
variable_bed_y_min: 0
variable_bed_y_max: 400
variable_bed_z_min: 0
variable_bed_z_max: 418

# Pause/Purge Positions
variable_tool0_pause_position_x: -20
variable_tool0_pause_position_y: -20
# tool1 variables only exist for dual nozzle printers
variable_tool1_pause_position_x: 720  # Only for dual nozzle
variable_tool1_pause_position_y: -110  # Only for dual nozzle

# Print cooling fans names
variable_fan0: 'extruder_CF'
variable_fan1: 'extruder1_CF'  # Only for dual nozzle printers

# [other printer-specific variables...]
gcode:
```

### From PRINTER_VARIABLES to Application Config

| PRINTER_VARIABLES | Application Config | Priority/Source |
|------------------|-------------------|-----------------|
| `bed_x_min`, `bed_x_max` | `machineBuildSize.X` | `max - min` |
| `bed_y_min`, `bed_y_max` | `machineBuildSize.Y` | `max - min` |
| `bed_z_min`, `bed_z_max` | `machineBuildSize.Z` | `max - min` |
| `bed_calibration_x1-4`, `bed_calibration_y1-4` | `calibrationPosition` | **Explicit values (preferred)** |
| Bed dimensions | `calibrationPosition` | Calculated fallback if explicit unavailable |
| `tool0_pause_position_x/y` | `tool0PurgePosition` | Direct mapping |
| `tool1_pause_position_x/y` | `tool1PurgePosition` | Direct mapping (dual nozzle only) |
| `is_dual_nozzle` | `IS_DUAL_NOZZLE` | **Explicit boolean (preferred)** |
| `ptfe_tube_length` | `ptfeTubeLength` | **Explicit value (preferred)** |
| X dimension | `ptfeTubeLength` | Calculated fallback: `round(X * 2.5 / 300) * 300` |

### Calibration Position Strategy

The system uses a **explicit-first, calculated-fallback** approach:

1. **Preferred**: Use explicit `variable_bed_calibration_**` coordinates
2. **Fallback**: Calculate from bed dimensions if explicit values unavailable

**Explicit Coordinates** (used when available):
- Direct mapping from `bed_calibration_x1-4` and `bed_calibration_y1-4`

**Calculated Fallback** (backwards compatibility):
- **X1, Y1**: 18% from left, 6% from front (front-left)
- **X2, Y2**: 85% from left, 6% from front (front-right)
- **X3, Y3**: 52% from left, 94% from front (back-center)
- **X4, Y4**: 52% from left, 59% from front (center)

## Usage

### For Developers

```python
# Get current printer configuration
config = printer_model.get_printer_configuration()
print(f"Build size: {config['machineBuildSize']}")
print(f"Dual nozzle: {config['IS_DUAL_NOZZLE']}")
print(f"Calibration positions: {config['calibrationPosition']}")

# Reload configuration after changes
printer_model.reload_printer_configuration()

# Listen for configuration changes
printer_model.printer_config_updated.connect(on_config_changed)

# Access printer configuration manager directly
from utils.printer_config_manager import get_printer_config_manager
manager = get_printer_config_manager()

# Get current active printer
current_printer = manager.get_current_printer_selection()
print(f"Active printer: {current_printer}")

# Get available printers
available_printers = manager.get_available_printers()
print(f"Available printers: {available_printers}")

# Parse variables from specific printer
variables = manager.parse_printer_variables_from_file("firmware/PRINTER_DRAGON_400.cfg")
config = manager.extract_printer_configuration(variables)
```

### Configuration File Management

The system follows Klipper's standard architecture:

1. **Development**: Edit files in `firmware/` directory
2. **Deployment**: Use `copy_firmware_files()` to deploy to `/home/pi/`
3. **Selection**: Update `printer.cfg` to activate specific printer configuration
4. **Automatic**: Parser automatically finds and loads active configuration

### Example Printer Setup

```python
from utils.printer_config_manager import copy_firmware_files

# Deploy all firmware files and activate DRAGON_400
success = copy_firmware_files("DRAGON_400")

# This will:
# 1. Copy all .cfg files to /home/pi/
# 2. Update printer.cfg to include PRINTER_DRAGON_400.cfg
# 3. Parser will automatically find PRINTER_VARIABLES in PRINTER_DRAGON_400.cfg
```

### Using the Configuration Manager

```python
from utils.printer_config_manager import (
    get_printer_config_manager,
    get_current_printer_selection,
    get_available_printers,
    get_printer_config_from_klipper
)

# Get complete configuration from active printer
config = get_printer_config_from_klipper()
if config:
    print(f"Machine build size: {config['machineBuildSize']}")
    print(f"Calibration positions: {config['calibrationPosition']}")
    print(f"Dual nozzle: {config['IS_DUAL_NOZZLE']}")

# Work with specific printer
manager = get_printer_config_manager()
variables = manager.get_printer_config_from_variables("DRAGON_400")
print(f"Printer config: {variables}")
```

## Benefits

1. **Correct Architecture**: Follows Klipper's intended configuration structure
2. **Automatic Configuration**: UI settings automatically match the active printer
3. **Explicit Configuration**: Uses explicit calibration positions and dual nozzle settings
4. **Reduced Maintenance**: No need to manually update multiple configuration files
5. **Consistency**: Single source of truth for printer specifications
6. **Flexibility**: Easy to add new printer variants by creating new PRINTER_*.cfg files
7. **Robustness**: Graceful fallback to defaults and calculated values if needed
8. **Backwards Compatibility**: Supports both new explicit variables and old calculated values

## Testing

The system includes comprehensive validation through the `PrinterConfigManager` class:

```python
# Test printer configuration parsing priority
from utils.printer_config_manager import get_printer_config_manager

manager = get_printer_config_manager()

# Test that it reads from deployed Klipper config first
current_printer = manager.get_current_printer_selection()
if current_printer:
    klipper_path = f"/home/pi/PRINTER_{current_printer}.cfg"
    firmware_path = f"firmware/PRINTER_{current_printer}.cfg"
    
    print(f"Testing configuration loading priority for {current_printer}:")
    print(f"Klipper config exists: {os.path.exists(klipper_path)}")
    print(f"Firmware config exists: {os.path.exists(firmware_path)}")
    
    config = manager.get_printer_config_from_klipper()
    if config:
        print(f"✅ Configuration loaded successfully")
        print(f"   Dual nozzle: {config['IS_DUAL_NOZZLE']}")
        print(f"   Build size: {config['machineBuildSize']}")
    else:
        print("❌ Failed to load configuration")

# Test all available printers
for printer in manager.get_available_printers():
    print(f"Testing {printer}...")
    variables = manager.get_printer_config_from_variables(printer)
    if variables:
        print(f"✅ {printer}: {variables['name']}")
        print(f"   Dual nozzle: {variables['is_dual']}")
        print(f"   Bed size: {variables['bed_width']}x{variables['bed_depth']}x{variables['bed_height']}")
    else:
        print(f"❌ {printer}: Failed to parse")
```

### Validation Tests

The system validates:
- All printer configurations can be properly parsed
- PRINTER_VARIABLES are in the correct location (PRINTER_<NAME>.cfg, not printer.cfg)
- Explicit bed calibration coordinates are used when available
- Dual nozzle detection works correctly (explicit `is_dual_nozzle` preferred)
- Fallback behavior for missing variables
- Configuration extraction and transformation
- OctoPrint configuration updates

## Implementation Details

### Variable Naming Conventions

- **New**: `variable_bed_calibration_x1` - Clear, descriptive naming
- **Old**: `variable_calibration_x1` - Supported for backwards compatibility
- **Explicit**: `variable_is_dual_nozzle` - Direct boolean setting
- **Fallback**: Fan detection - Used if explicit setting unavailable

### Parser Priority Order

1. **Active Printer Detection**: Parse `printer.cfg` to find included printer file
2. **Klipper Directory First**: Look for variables in `/home/pi/PRINTER_<NAME>.cfg` (deployed location where Klipper reads from)
3. **Firmware Directory Fallback**: If not found in Klipper directory, try `firmware/PRINTER_<NAME>.cfg`
4. **Variable Parsing**: Extract all `variable_*` entries from `PRINTER_VARIABLES` macro
5. **Type Conversion**: Parse strings, numbers, and booleans correctly
6. **Configuration Transformation**: Convert raw variables to application format
7. **Fallback Values**: Use defaults from `config.py` if variables missing

### Configuration File Integration

**PrinterConfigManager** handles:
- **Klipper Configuration**: Copies firmware files, updates printer.cfg includes
- **OctoPrint Configuration**: Updates config.yaml and printer profiles
- **Backup Management**: Creates and restores configuration backups
- **Validation**: Checks configuration file integrity

### API Design

**Singleton Pattern**: Single instance accessed via `get_printer_config_manager()`

**Convenience Functions**: Backwards-compatible wrapper functions:
```python
from utils.printer_config_manager import (
    get_available_printers,
    get_current_printer_selection, 
    copy_firmware_files,
    get_printer_config_from_klipper
)
```

**Error Handling**: Graceful fallbacks and comprehensive logging

## Backwards Compatibility

The system maintains robust backwards compatibility through multiple fallback layers:

### Variable Name Compatibility
- **New naming**: `variable_bed_calibration_**` (preferred)
- **Old naming**: `variable_calibration_**` (still supported)
- **Dual nozzle**: Explicit `variable_is_dual_nozzle` preferred, fan detection fallback

### Configuration Sources
1. **Primary**: Explicit variables in active printer configuration
2. **Secondary**: Calculated values from bed dimensions and hardware detection
3. **Tertiary**: Hardcoded defaults in `config.py`

### API Compatibility
- Same variable names in `config.py` maintained
- Existing code accessing configuration variables continues to work
- No breaking changes to external interfaces

## Current Status

### ✅ Completed Features

1. **Unified PrinterConfigManager**
   - Single class handling all printer configuration operations
   - Supports both Klipper and OctoPrint configuration management
   - Automatic PyYAML installation for YAML parsing

2. **Explicit Configuration Values**
   - `variable_bed_calibration_x1-4`, `variable_bed_calibration_y1-4`
   - `variable_is_dual_nozzle` with proper boolean values (0/1)
   - `variable_ptfe_tube_length` with explicit values
   - Clear variable naming with `bed_calibration_**` prefix

3. **Architecture-Correct Parser**
   - Looks for PRINTER_VARIABLES in `firmware/PRINTER_<NAME>.cfg` files
   - Proper active printer detection from include statements
   - Robust variable parsing with type conversion (int, float, bool, string)

4. **Dual Nozzle Handling**
   - Single nozzle printers: `is_dual_nozzle: 0`, no tool1 variables
   - Dual nozzle printers: `is_dual_nozzle: 1`, full tool1 configuration
   - Clean separation of single vs dual nozzle configurations

5. **Complete File Management**
   - Firmware file deployment via `copy_firmware_files()`
   - OctoPrint configuration updates (config.yaml, printer profiles)
   - Backup and restore functionality
   - Configuration validation and integrity checks

6. **Integration Points**
   - Automatic loading in PrinterModel initialization
   - WebSocket connection triggers configuration reload
   - Printer setup workflow uses unified manager

### 📋 Printer Configuration Status

| Printer | Type | is_dual_nozzle | Bed Calibration | Z-Height | Status |
|---------|------|----------------|-----------------|----------|---------|
| DRAGON_400 | Single | 0 | Explicit coordinates | 418mm | ✅ Complete |
| DRAGON_500 | Single | 0 | Explicit coordinates | 418mm | ✅ Complete |
| TWINDRAGON_600 | Dual | 1 | Explicit coordinates | 414mm | ✅ Complete |
| TWINDRAGON_600x300 | Dual | 1 | Explicit coordinates | 414mm | ✅ Complete |

**Configuration Features by Printer**:
- **All Printers**: Explicit `variable_is_dual_nozzle`, `variable_ptfe_tube_length`
- **All Printers**: Complete bed calibration coordinates (X1-4, Y1-4)
- **All Printers**: Full bed dimension specification (X/Y/Z min/max)
- **Single Nozzle**: Only tool0 pause positions, single fan configuration
- **Dual Nozzle**: Full tool0/tool1 pause positions, dual fan configuration

## Future Enhancements

Potential improvements for future development:
- **Real-time configuration updates** when Klipper config changes
- **Configuration validation UI** with error reporting
- **Additional printer-specific settings** (temperatures, speeds, acceleration)
- **Dynamic macro variable** support for runtime configuration changes
- **Configuration export/import** for backup and sharing
- **Printer configuration wizard** for new printer setup
