"""Support for Satel Integra zone states- represented as binary sensors."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta

from satel_integra_enh import AsyncSatel

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_ZONES_UPDATED,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
    SatelConfigEntry,
)
from .entity import SatelIntegraEntity

_LOGGER = logging.getLogger(__name__)

# Temperature polling interval - 5 minutes to avoid overwhelming the connection
# Temperature doesn't change rapidly in smoke detectors, so slow polling is acceptable
TEMPERATURE_SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra binary sensor devices."""

    controller = config_entry.runtime_data

    zone_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_ZONE,
        config_entry.subentries.values(),
    )

    for subentry in zone_subentries:
        zone_num: int = subentry.data[CONF_ZONE_NUMBER]
        zone_type: BinarySensorDeviceClass = subentry.data[CONF_ZONE_TYPE]

        async_add_entities(
            [
                SatelIntegraBinarySensor(
                    controller,
                    config_entry.entry_id,
                    subentry,
                    zone_num,
                    zone_type,
                    SIGNAL_ZONES_UPDATED,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )

    output_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_OUTPUT,
        config_entry.subentries.values(),
    )

    for subentry in output_subentries:
        output_num: int = subentry.data[CONF_OUTPUT_NUMBER]
        ouput_type: BinarySensorDeviceClass = subentry.data[CONF_ZONE_TYPE]

        async_add_entities(
            [
                SatelIntegraBinarySensor(
                    controller,
                    config_entry.entry_id,
                    subentry,
                    output_num,
                    ouput_type,
                    SIGNAL_OUTPUTS_UPDATED,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraBinarySensor(SatelIntegraEntity, BinarySensorEntity):
    """Representation of an Satel Integra binary sensor."""

    def __init__(
        self,
        controller: AsyncSatel,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
        device_class: BinarySensorDeviceClass,
        react_to_signal: str,
    ) -> None:
        """Initialize the binary_sensor."""
        super().__init__(
            controller,
            config_entry_id,
            subentry,
            device_number,
        )

        self._attr_device_class = device_class
        self._react_to_signal = react_to_signal
        self._temperature: float | None = None

        # Enable polling only for motion sensors (IR sensors often have temperature capability)
        # Only zones (not outputs) with motion device class are polled
        # Auto-disable handles zones without temperature after first poll attempt
        self._attr_should_poll = (
            react_to_signal == SIGNAL_ZONES_UPDATED
            and device_class == BinarySensorDeviceClass.MOTION
        )

        # Set scan interval for temperature polling (5 minutes)
        if self._attr_should_poll:
            self._scan_interval = TEMPERATURE_SCAN_INTERVAL

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        # Call parent to handle area assignment
        await super().async_added_to_hass()

        if self._react_to_signal == SIGNAL_OUTPUTS_UPDATED:
            self._attr_is_on = self._device_number in self._satel.violated_outputs
        else:
            self._attr_is_on = self._device_number in self._satel.violated_zones

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._react_to_signal, self._devices_updated
            )
        )

    @callback
    def _devices_updated(self, zones: dict[int, int]):
        """Update the zone's state, if needed."""
        if self._device_number in zones:
            new_state = zones[self._device_number] == 1
            if new_state != self._attr_is_on:
                self._attr_is_on = new_state
                self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, float] | None:
        """Return temperature as an extra attribute if available."""
        if self._temperature is not None:
            return {"temperature": self._temperature}
        return None

    async def async_update(self) -> None:
        """Poll temperature for motion sensor zones.

        Only called if should_poll is True (motion sensor zones only).
        Polling interval is controlled by TEMPERATURE_SCAN_INTERVAL.

        Random delay spreads requests across the full 5-minute polling interval
        to prevent overwhelming the alarm panel connection.
        """
        if not self._attr_should_poll:
            return

        # Add random delay (0-240 seconds, 80% of 5-minute interval)
        # This spreads temperature requests across the entire polling cycle
        # instead of all hitting within the first few seconds
        delay = random.uniform(0, 240)
        _LOGGER.debug(
            "Zone %s ('%s') waiting %.1fs (%.1f min) before temperature poll",
            self._device_number,
            self.name,
            delay,
            delay / 60,
        )
        await asyncio.sleep(delay)

        try:
            # Request temperature from the zone
            # Protocol allows up to 5 seconds for response
            temperature = await self._satel.get_zone_temperature(self._device_number)

            if temperature is not None:
                _LOGGER.debug(
                    "Zone %s ('%s') temperature: %.1f°C",
                    self._device_number,
                    self.name,
                    temperature,
                )
                self._temperature = temperature
            else:
                # Zone doesn't support temperature or returned undetermined
                # Disable polling for this zone to avoid future unnecessary requests
                if self._temperature is None:
                    _LOGGER.info(
                        "Zone %s ('%s') does not support temperature - disabling temperature polling",
                        self._device_number,
                        self.name,
                    )
                    self._attr_should_poll = False

        except asyncio.TimeoutError:
            _LOGGER.debug(
                "Timeout reading temperature for zone %s - zone may not support temperature",
                self._device_number,
            )
            # Disable polling if we never got a temperature reading
            if self._temperature is None:
                self._attr_should_poll = False

        except Exception as ex:
            _LOGGER.warning(
                "Error reading temperature for zone %s: %s",
                self._device_number,
                ex,
            )
