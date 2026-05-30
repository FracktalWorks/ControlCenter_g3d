# Simplified Nozzle Offset Calibration - Implementation Summary

## Overview
The nozzle offset calibration process has been completely simplified to remove automatic nozzle detection and rely entirely on user manual positioning. This makes the process more reliable and easier to maintain.

## New Workflow

### Step 1: Clean Nozzles
- Home the printer
- Set Z to 50mm
- Set IDEX mode to Mirror (DUPLICATION)
- Position at front of bed (X67, Y20) - 1/3 from left
- Heat both nozzles to 80°C
- Send M503 to get latest tool offsets
- User cleans both nozzle tips with wire brush

### Step 2: Connect Camera
- Set regular mode (PRIMARY) and activate T0
- Move to center front position (X100, Y20, Z30)
- User connects USB calibration camera and places below nozzle

### Step 3: Position T0 (Course)
- Camera starts with 1x zoom
- Movement step resolution: 0.5mm
- Red crosshair circle (10px radius) overlay on camera feed
- User manually positions T0 nozzle to center of crosshair using X/Y/Z buttons

### Step 4: Position T0 (Fine)
- Camera zooms to 2x
- Movement step resolution: 0.01mm  
- Red crosshair circle (15px radius) overlay
- User fine-tunes T0 position
- M114 sent to record T0 position

### Step 5: Position T1 (Course)
- Z moves down 5mm, switch to T1, Z moves back up 5mm
- Camera at 1x zoom, 0.5mm steps
- User positions T1 nozzle coarsely

### Step 6: Position T1 (Fine)
- Camera zooms to 2x, 0.01mm steps
- User fine-tunes T1 position
- M114 sent to record T1 position

### Step 7: Results
- Calculate offset differences: T1_pos - T0_pos
- Add to current offsets: new_offset = current_offset + difference
- Apply using M218 T1 X{new_x} Y{new_y}
- Save with SAVE_CONFIG
- Show success dialog with applied offsets

## Key Changes Made

### Files Modified
- **cameraToolOffsetCalibration.py**: Complete rewrite with simplified workflow
- **nozzle_detector.py**: Deleted (no longer needed)

### Removed Features
- Automatic nozzle detection algorithms
- Complex image processing
- NozzleDetector class
- OpenCV automatic installation (now optional)

### Added Features
- Manual crosshair overlay on camera feed
- Dynamic zoom levels (1x for course, 2x for fine)
- Variable movement step resolution (0.5mm course, 0.01mm fine)
- Proper tool switching with Z clearance
- M503/M114 integration for position tracking
- Error handling for camera connection failures

### Technical Improvements
- Cleaner, more maintainable code structure
- Follows established wizard patterns (like nozzleChangeWizard)
- Proper resource cleanup and thread management
- Better error handling and user feedback
- Consistent with bed leveling wizard patterns for M114/position tracking

## Benefits
1. **Reliability**: No dependency on computer vision algorithms
2. **Simplicity**: User-controlled process with clear steps
3. **Maintainability**: Much simpler codebase
4. **Flexibility**: Works with any camera or lighting conditions
5. **Accuracy**: User can achieve sub-millimeter precision with fine positioning

## Integration
The wizard integrates seamlessly with the existing calibration system and follows the same patterns as other wizards in the codebase. It properly handles:
- Websocket position updates
- Tool offset calculations (matching bed leveling wizard)
- Dialog management
- Resource cleanup
- Error handling
