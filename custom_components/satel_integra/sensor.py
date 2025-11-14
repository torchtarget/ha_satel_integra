"""Support for Satel Integra zone temperature sensors."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from satel_integra_enh import AsyncSatel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ZONE_NUMBER,
    SUBENTRY_TYPE_ZONE,
    SatelConfigEntry,
)
from .entity import SatelIntegraEntity

_LOGGER = logging.getLogger(__name__)

# Poll interval for temperature readings (in seconds)
# Note: Temperature requests can take up to 5 seconds per protocol spec
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra temperature sensor devices with auto-detection."""

    controller = config_entry.runtime_data

    # Get all zone subentries
    zone_subentries = list(
        filter(
            lambda entry: entry.subentry_type == SUBENTRY_TYPE_ZONE,
            config_entry.subentries.values(),
        )
    )

    if not zone_subentries:
        return

    async def test_zone_temperature(subentry: ConfigSubentry, delay: float = 0) -> ConfigSubentry | None:
        """Test if a zone supports temperature and return subentry if it does."""
        zone_num: int = subentry.data[CONF_ZONE_NUMBER]

        # Add small delay to avoid overwhelming controller
        if delay > 0:
            await asyncio.sleep(delay)

        _LOGGER.debug("Testing zone %s ('%s') for temperature capability", zone_num, subentry.data[CONF_NAME])

        try:
            # Try to read temperature with 6-second timeout (protocol spec: up to 5 seconds + margin)
            temperature = await asyncio.wait_for(
                controller.get_zone_temperature(zone_num),
                timeout=6.0
            )

            if temperature is not None:
                _LOGGER.info(
                    "✅ Zone %s ('%s') supports temperature: %.1f°C - creating sensor",
                    zone_num,
                    subentry.data[CONF_NAME],
                    temperature,
                )
                return subentry
            else:
                _LOGGER.debug("Zone %s ('%s') returned None (no temperature sensor)", zone_num, subentry.data[CONF_NAME])
                return None

        except asyncio.TimeoutError:
            _LOGGER.debug(
                "Zone %s ('%s') timeout after 6s (no temperature sensor)",
                zone_num,
                subentry.data[CONF_NAME],
            )
            return None
        except Exception as ex:
            _LOGGER.warning(
                "Zone %s ('%s') temperature check error: %s",
                zone_num,
                subentry.data[CONF_NAME],
                ex,
            )
            return None

    # Test all zones in parallel with small stagger to avoid overwhelming controller
    _LOGGER.info("Testing %d zones for temperature capability (6s timeout per zone)", len(zone_subentries))
    results = await asyncio.gather(
        *[test_zone_temperature(subentry, delay=i * 0.05) for i, subentry in enumerate(zone_subentries)],
        return_exceptions=True
    )

    # Create temperature sensors for zones that support it
    temperature_sensors = []
    for subentry in results:
        if isinstance(subentry, ConfigSubentry):
            zone_num: int = subentry.data[CONF_ZONE_NUMBER]
            temperature_sensors.append(
                SatelIntegraTemperatureSensor(
                    controller,
                    config_entry.entry_id,
                    subentry,
                    zone_num,
                )
            )

    if temperature_sensors:
        _LOGGER.info("Created %d temperature sensors", len(temperature_sensors))
        async_add_entities(temperature_sensors)
    else:
        _LOGGER.info("No temperature-capable zones detected")


class SatelIntegraTemperatureSensor(SatelIntegraEntity, SensorEntity):
    """Representation of a Satel Integra temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = True

    def __init__(
        self,
        controller: AsyncSatel,
        config_entry_id: str,
        subentry: ConfigSubentry,
        zone_number: int,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(
            controller,
            config_entry_id,
            subentry,
            zone_number,
        )

        # Override unique_id to make it specific to temperature sensor
        # Use "temperature" suffix to avoid conflict with zone binary sensor
        self._attr_unique_id = f"{config_entry_id}_zones_{zone_number}_temperature"

        # Update entity name to include "Temperature"
        self._attr_name = "Temperature"

    async def async_update(self) -> None:
        """Fetch new temperature value from the zone."""
        try:
            temperature = await self._satel.get_zone_temperature(self._device_number)

            if temperature is not None:
                self._attr_native_value = temperature
                self._attr_available = True
            else:
                # Temperature is None - zone may not support temperature or is offline
                # Keep the sensor available but with unknown state
                self._attr_native_value = None
                self._attr_available = True

        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout reading temperature for zone %s - marking unavailable",
                self._device_number,
            )
            self._attr_available = False
        except Exception as ex:
            _LOGGER.error(
                "Error reading temperature for zone %s: %s",
                self._device_number,
                ex,
            )
            self._attr_available = False
