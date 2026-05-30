# Dragon 400 V2 Dual Material Bay - Hardware Test Cases

## Pre-Test Setup
- [ ] Flash PRINTER_DRAGON_400_V2.cfg to Klipper
- [ ] Verify `has_dual_material_bay: 1` in PRINTER_VARIABLES
- [ ] Restart Klipper and ControlCenter application

---

## 1. UI Visibility Tests

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **1.1 Bay B UI Visible** | Open Filament Management screen | Bay B frame, label, change button, edit button all visible | |
| **1.2 Bay A Still Works** | Verify Bay A elements | Bay A elements unchanged and functional | |
| **1.3 Tool1 Hidden (Single Nozzle)** | Check Tool1/Bay X section | Tool1 section hidden (Dragon 400 V2 is single nozzle) | |

---

## 2. Motor Sync Tests

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **2.1 Bay A Motor Sync** | Click Bay A "Change Filament" → observe console | `SYNC_MATERIAL_BAY BAY=A` sent, "Material Bay A activated" | |
| **2.2 Bay B Motor Sync** | Click Bay B "Change Filament" → observe console | `SYNC_MATERIAL_BAY BAY=B` sent, "Material Bay B activated" | |
| **2.3 Motor Movement Bay A** | With Bay A synced, manually extrude 10mm | Only `extruder_side0` motor moves | |
| **2.4 Motor Movement Bay B** | With Bay B synced, manually extrude 10mm | Only `extruder_side1` motor moves | |
| **2.5 Query Active Bay** | Send `GET_ACTIVE_MATERIAL_BAY` G-code | Reports correct active bay | |

---

## 3. Filament Load Tests

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **3.1 Load Bay A** | Bay A → Change Filament → Select material → Load | Correct motor drives, extrudes full PTFE length (1310mm) | |
| **3.2 Load Bay B** | Bay B → Change Filament → Select material → Load | Correct motor drives, extrudes full PTFE length (1310mm) | |
| **3.3 Bay A State Persisted** | Load Bay A, complete wizard, check UI | Bay A shows "Loaded" with filament name | |
| **3.4 Bay B State Persisted** | Load Bay B, complete wizard, check UI | Bay B shows "Loaded" with filament name | |
| **3.5 Home Screen Active Bay** | Load Bay B, go to Home screen | Home screen shows Bay B filament (not Bay A) | |

---

## 4. Filament Unload Tests

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **4.1 Unload Bay A** | Bay A → Change Filament → Unload | Retracts full PTFE length (1310mm) via correct motor | |
| **4.2 Unload Bay B** | Bay B → Change Filament → Unload | Retracts full PTFE length (1310mm) via correct motor | |
| **4.3 Bay State After Unload** | Unload Bay A, complete wizard | Bay A shows "Empty", filament cleared | |

---

## 5. Sensor Tests

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **5.1 Bay A Runout Detection** | Enable sensors, start print, trigger T0 runout | Print pauses, dialog shows "Filament runout detected on T0" | |
| **5.2 Bay B Runout Detection** | Sync Bay B, enable sensors, start print, trigger Bay B runout | Print pauses, dialog shows "Filament runout detected on T0" | |
| **5.3 Bay A Jam Detection** | Enable jam sensor, cause jam on Bay A | Print pauses, dialog shows "Filament Jam Detected on T0" | |
| **5.4 Bay B Jam Detection** | Sync Bay B, enable jam sensor, cause jam on Bay B | Print pauses, dialog shows "Filament Jam Detected on T0" | |
| **5.5 Sensors Disabled at Startup** | Restart Klipper, check sensor state | All bay sensors disabled by default | |

---

## 6. Persistence Tests

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **6.1 Python Persistence** | Load Bay B, restart ControlCenter app | Bay B still shows as loaded with filament | |
| **6.2 Klipper Persistence** | Load Bay B, send `SAVE_ACTIVE_BAY`, restart Klipper | `DUAL_BAY_STARTUP` restores Bay B as active | |
| **6.3 Active Bay Restored** | Sync Bay B, restart Klipper, send `GET_ACTIVE_MATERIAL_BAY` | Reports "Active Material Bay: B" | |
| **6.4 Edit Dialog Persistence** | Use Edit button to change Bay B filament/status | Changes persist after app restart | |

---

## 7. Backward Compatibility Tests (on Twin Dragon / Dragon 400 V1)

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **7.1 Bay B UI Hidden** | Open Filament Management on Twin Dragon | No Bay B elements visible | |
| **7.2 No Dual Bay Errors** | Open ControlCenter, navigate all screens | No errors about missing Bay B elements | |
| **7.3 Standard PTFE Length** | Load filament on Twin Dragon | Uses standard `ptfeTubeLength` (not 1310mm) | |
| **7.4 Sensor Messages Work** | Trigger runout on Twin Dragon | Correct "Filament Runout Detected on T0/T1" handling | |

---

## 8. Edge Cases

| Test | Steps | Expected Result | Pass/Fail |
|------|-------|-----------------|-----------|
| **8.1 Cancel Mid-Load** | Start Bay B load, cancel during extrusion | Motor stops, no crash, can retry | |
| **8.2 Switch Bays Mid-Session** | Load Bay A, then load Bay B without unload | Motor switches correctly, no binding | |
| **8.3 Power Cycle During Print** | Start print with Bay B, power cycle | Active bay restored, can resume | |
| **8.4 Rapid Bay Switching** | Quickly switch Bay A → B → A via console | No motor conflicts, correct sync each time | |
| **8.5 Unsync All** | Send `UNSYNC_ALL_MATERIAL_BAYS` | Both motors unsynced, sensors disabled | |

---

## 9. Console G-Code Verification

Run these commands manually via console/terminal to verify firmware functionality:

```gcode
# Test commands to run manually:
SYNC_MATERIAL_BAY BAY=A       # Should activate Bay A
SYNC_MATERIAL_BAY BAY=B       # Should activate Bay B
GET_ACTIVE_MATERIAL_BAY       # Should report active bay
SAVE_ACTIVE_BAY               # Should persist to variables.cfg
UNSYNC_ALL_MATERIAL_BAYS      # Should unsync both motors

# Motor test (after syncing):
G91
G1 E10 F300                   # Extrude 10mm - verify correct motor moves
G1 E-10 F300                  # Retract 10mm
G90
```

---

## Test Completion Summary

| Section | Tests Passed | Tests Failed | Notes |
|---------|--------------|--------------|-------|
| 1. UI Visibility | /3 | | |
| 2. Motor Sync | /5 | | |
| 3. Filament Load | /5 | | |
| 4. Filament Unload | /3 | | |
| 5. Sensors | /5 | | |
| 6. Persistence | /4 | | |
| 7. Backward Compat | /4 | | |
| 8. Edge Cases | /5 | | |
| **TOTAL** | **/34** | | |

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Tester | | | |
| Developer | | | |
| QA Lead | | | |

---

## Issues Found

| Issue # | Test Case | Description | Severity | Status |
|---------|-----------|-------------|----------|--------|
| | | | | |
| | | | | |
| | | | | |

---

## Notes

_Add any additional observations or notes here:_

