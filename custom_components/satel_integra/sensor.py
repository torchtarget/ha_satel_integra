"""Support for Satel Integra zone temperature sensors."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from satel_integra import AsyncSatel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ZONE_NUMBER,
    SUBENTRY_TYPE_TEMPERATURE_ZONE,
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
    """Set up the Satel Integra temperature sensor devices."""

    controller = config_entry.runtime_data

    temperature_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_TEMPERATURE_ZONE,
        config_entry.subentries.values(),
    )

    for subentry in temperature_subentries:
        zone_num: int = subentry.data[CONF_ZONE_NUMBER]

        async_add_entities(
            [
                SatelIntegraTemperatureSensor(
                    controller,
                    config_entry.entry_id,
                    subentry,
                    zone_num,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


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
