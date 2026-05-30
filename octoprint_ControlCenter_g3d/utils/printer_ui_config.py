"""
Printer UI Configuration Module

This module handles printer configuration (single vs dual nozzle) and manages
which UI elements should be shown/hidden based on the printer type.
"""

import config
from utils.logger import get_logger

logger = get_logger(__name__)

def is_dual_nozzle_printer():
    """Check if the printer is configured for dual nozzle operation."""
    # Access the current value dynamically to pick up changes from Klipper config loading
    return config.IS_DUAL_NOZZLE

def is_dual_material_bay_printer():
    """Check if the printer has dual material bays (Dragon 400 V2).
    
    Dual material bay = 2 extruder motors feeding into single nozzle via Y-splitter.
    """
    # Allow debug override for testing
    if config.DEBUG_FORCE_DUAL_MATERIAL_BAY:
        return True
    return config.HAS_DUAL_MATERIAL_BAY

# UI elements that should be hidden for single nozzle printers
DUAL_NOZZLE_ELEMENTS = {
    'home_screen': [
        'tool1Layout', 'tool1Label', 'tool1LoadedNozzle', 'tool1LoadedFilament',
        'tool1TargetTemperature', 'tool1TempBar', 'tool1ActualTemperature', 'tool1TextLabel', 'toolSeperationLine'
    ],
    'control_screen': [
        'toolToggleTemperatureButton', 'toolToggleMotionButton'
    ],
    'filament_management_screen': [
        'changeTool1MaterialBayX', 'tool1Frame', 'editTool1MaterialBayX',
        'tool11MaterialBayXStateColor', 'tool1MaterialBayXStateLabel', 'changeTool1Button',
        'tool1MaterialBayXLabel'
    ],
    'calibrate_screen': [
        'idexCalibrationWizardButton', 'toolOffsetZButton', 'toolOffsetXYButton',
        'cameraToolOffsetCalibrateButton', 'toolZOffsetWizardButton'
    ]
}

# UI elements that should only be shown for dual material bay printers (Dragon 400 V2)
# These elements are hidden by default in the .ui file and shown only when is_dual_material_bay_printer() is True
# NOTE: Do NOT include Bay A elements here - they should always be visible
DUAL_MATERIAL_BAY_ONLY_ELEMENTS = {
    'filament_management_screen': [
        # Bay B frame and elements - only visible on Dragon 400 V2
        'tool0MaterialBayBFrame',  # Main container for Bay B
        'tool0MaterialBayBLabel', 'tool0MaterialBayBStateLabel', 'tool0MaterialBayBStateColor',
        'changeTool0MaterialBayB', 'editTool0MaterialBayB',
        # Bay selector buttons (optional - may not exist in current UI)
        'tool0BayAButton', 'tool0BayBButton',
        # Dual bay frame container (optional)
        'tool0DualBayFrame',
        # Bay active indicator (optional)
        'tool0BayActiveIndicator'
    ]
}

def hide_dual_nozzle_elements(widget, element_names):
    """
    Hide specified UI elements if printer is configured for single nozzle.
    
    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to hide for single nozzle printers
    """
    if not is_dual_nozzle_printer():
        for element_name in element_names:
            element = getattr(widget, element_name, None)
            if element:
                try:
                    element.hide()
                    logger.debug(f"Hidden dual nozzle element: {element_name}")
                except Exception as e:
                    logger.error(f"Error hiding element {element_name}: {e}")

def force_single_tool(requested_tool):
    """
    Force tool1 requests to tool0 for single nozzle printers.
    
    Args:
        requested_tool: The requested tool ("tool0" or "tool1")
        
    Returns:
        str: "tool0" for single nozzle printers, original tool for dual nozzle
    """
    if requested_tool == "tool1" and not is_dual_nozzle_printer():
        logger.info("Forced tool1 to tool0 for single nozzle configuration")
        return "tool0"
    return requested_tool

def get_dual_nozzle_elements(screen_name):
    """
    Get the list of dual nozzle elements for a specific screen.
    
    Args:
        screen_name: Name of the screen (e.g., 'home_screen', 'control_screen')
        
    Returns:
        list: List of element names to hide for single nozzle printers
    """
    return DUAL_NOZZLE_ELEMENTS.get(screen_name, [])

def apply_nozzle_config_to_screen(widget, screen_name):
    """
    Apply nozzle configuration to a specific screen widget.
    
    Args:
        widget: The screen widget
        screen_name: Name of the screen for element lookup
    """
    hide_dual_nozzle_elements(widget, get_dual_nozzle_elements(screen_name))

def apply_nozzle_config_to_all_screens(main_window):
    """
    Apply nozzle configuration to all screens in the main window.
    
    Args:
        main_window: The main window containing all screen widgets
    """
    if not is_dual_nozzle_printer():
        try:
            for screen_name, elements in DUAL_NOZZLE_ELEMENTS.items():
                if hasattr(main_window, screen_name):
                    screen = getattr(main_window, screen_name)
                    hide_dual_nozzle_elements(screen, elements)
                    
            logger.info("Successfully applied single nozzle configuration to all screens")
        except Exception as e:
            logger.error(f"Error applying nozzle configuration: {e}")
    else:
        logger.info("Dual nozzle configuration active - all elements visible")

def get_dual_material_bay_elements(screen_name):
    """
    Get the list of dual material bay elements for a specific screen.
    
    Args:
        screen_name: Name of the screen (e.g., 'filament_management_screen')
        
    Returns:
        list: List of element names that are only for dual material bay printers
    """
    return DUAL_MATERIAL_BAY_ONLY_ELEMENTS.get(screen_name, [])

def show_dual_material_bay_elements(widget, element_names):
    """
    Show specified UI elements only if printer has dual material bays.
    These elements are hidden by default in the .ui file.
    
    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to show for dual material bay printers
    """
    if is_dual_material_bay_printer():
        for element_name in element_names:
            element = getattr(widget, element_name, None)
            if element:
                try:
                    element.show()
                    logger.debug(f"Shown dual material bay element: {element_name}")
                except Exception as e:
                    logger.error(f"Error showing element {element_name}: {e}")

def hide_dual_material_bay_elements(widget, element_names):
    """
    Hide dual material bay elements for non-dual material bay printers.
    
    Args:
        widget: The parent widget containing the elements
        element_names: List of element names to hide for non-dual material bay printers
    """
    if not is_dual_material_bay_printer():
        for element_name in element_names:
            element = getattr(widget, element_name, None)
            if element:
                try:
                    element.hide()
                    logger.debug(f"Hidden dual material bay element: {element_name}")
                except Exception as e:
                    logger.error(f"Error hiding element {element_name}: {e}")

def apply_dual_material_bay_config_to_screen(widget, screen_name):
    """
    Apply dual material bay configuration to a specific screen widget.
    Shows elements for dual material bay printers, hides otherwise.
    
    Args:
        widget: The screen widget
        screen_name: Name of the screen for element lookup
    """
    elements = get_dual_material_bay_elements(screen_name)
    if is_dual_material_bay_printer():
        show_dual_material_bay_elements(widget, elements)
    else:
        hide_dual_material_bay_elements(widget, elements)
