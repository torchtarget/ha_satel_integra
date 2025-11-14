# Satel Integra Enhanced for Home Assistant

Enhanced custom component for Home Assistant to integrate with Satel Integra alarm systems.

## About

This is an enhanced version of the Satel Integra integration, based on the official Home Assistant component. It adds encryption support and additional protocol features not available in the official integration.

## Current Status

**v0.3.0 - Encryption Support Added!** - Now supports encrypted communication with Satel Integra alarm panels.

- Based on official HA core satel_integra component
- Uses latest `satel_integra` library from GitHub (unreleased, post-0.3.7)
- Updated to new library API with improved lifecycle management
- **✅ Encryption support via integration_key parameter**
- Includes config flow for UI-based setup
- Supports partitions, zones, outputs, and switchable outputs

## Features

- **Encrypted Communication**: Supports integration key for secure communication with your alarm panel
- **Alarm Control Panel**: Arm/disarm partitions with different modes (Away, Home)
- **Binary Sensors**: Monitor zone states (doors, windows, motion detectors, etc.)
- **Switches**: Control switchable outputs (gates, lights, etc.)
- **Real-time Updates**: Instant notifications when zone states change
- **Multi-Partition Support**: Manage multiple alarm partitions independently

## Planned Features

- [ ] Temperature monitoring
- [ ] System diagnostics/trouble sensors
- [ ] Zone bypass functionality
- [ ] Zone tamper detection
- [ ] Event log reading
- [ ] RTC/clock synchronization

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations" section
3. Click the three dots menu (⋮) in the top right
4. Select "Custom repositories"
5. Add repository URL: `https://github.com/torchtarget/ha_satel_integra_enh`
6. Select category: "Integration"
7. Click "Add"
8. Find "Satel Integra Enhanced" in the list and click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Extract the `custom_components/satel_integra` directory to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Satel Integra"**
3. Enter the following information:
   - **Host**: IP address of your ETHM-1 Plus module
   - **Port**: TCP port (default: 7094)
   - **Code** (optional): Alarm code for controlling switchable outputs
   - **Integration Key** (optional): Encryption key for secure communication
4. Click **Submit**
5. Add partitions, zones, outputs, and switchable outputs as needed

### Finding Your Integration Key

The integration key (also called "integration password") is configured on your Satel Integra panel:
1. Enter installer mode on your alarm panel
2. Navigate to the ETHM-1 Plus module settings
3. Look for "Integration" or "INTEGRATION" settings
4. The integration key is a hexadecimal string (e.g., `0123456789ABCDEF0123456789ABCDEF`)

**Note**: If your panel requires encryption and you don't provide the integration key, the connection will fail with "No response received from panel" errors.

## Credits

- Original integration by @c-soft (Krzysztof Machelski)
- Official HA component maintained by @Tommatheussen
- Encryption library work by @wasilukm

## License

This component follows the same license as Home Assistant Core (Apache 2.0)
