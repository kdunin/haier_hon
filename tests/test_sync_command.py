"""Regression tests for syncing a command's parameters into "settings".

Some Haier AC models ship a ``stopProgram`` command whose ancillary
parameter ``windDirectionVerticalPositionSequence`` defaults to 0 while its
allowed values are 2-8. ``HonAppliance.sync_command`` raised a ValueError on
that parameter, so turning the AC off from Home Assistant failed with an
"Unexpected exception" after the stop command had already been sent.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate import HVACMode
from pyhon.appliance import HonAppliance
from pyhon.parameter.enum import HonParameterEnum
from pyhon.parameter.range import HonParameterRange

from hon.climate import HonACClimateEntity
from hon.util import sync_command

VERTICAL = ["2", "4", "5", "6", "7", "8"]


def enum(key: str, values: list[str], default: str, group: str) -> HonParameterEnum:
    attributes: dict[str, Any] = {"enumValues": values}
    if default:
        attributes["defaultValue"] = default
    return HonParameterEnum(key, attributes, group)


def on_off(default: str) -> HonParameterRange:
    return HonParameterRange(
        "onOffStatus",
        {
            "minimumValue": 0,
            "maximumValue": 1,
            "incrementValue": 1,
            "defaultValue": default,
        },
        "parameters",
    )


def make_command(name: str, parameters: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(name=name, parameters=parameters, send=AsyncMock())


def make_appliance() -> HonAppliance:
    appliance = HonAppliance(None, {"applianceTypeName": "AC"})
    seq = "windDirectionVerticalPositionSequence"
    appliance._commands = {
        "settings": make_command(
            "settings",
            {
                "onOffStatus": on_off("1"),
                seq: enum(seq, VERTICAL, "5", "ancillaryParameters"),
                "windDirectionVertical": enum(
                    "windDirectionVertical", VERTICAL, "5", "parameters"
                ),
            },
        ),
        "stopProgram": make_command(
            "stopProgram",
            {
                "onOffStatus": on_off("0"),
                # No defaultValue: pyhon falls back to "0", which is not
                # one of the allowed values (as seen on AS25PBAHRA units).
                seq: enum(seq, VERTICAL, "", "ancillaryParameters"),
                "windDirectionVertical": enum(
                    "windDirectionVertical", VERTICAL, "7", "parameters"
                ),
            },
        ),
    }
    return appliance


def test_pyhon_sync_command_raises_on_out_of_range_default() -> None:
    """Documents the upstream behaviour this integration works around."""
    appliance = make_appliance()
    with pytest.raises(ValueError):
        appliance.sync_command("stopProgram", "settings")


def test_sync_command_skips_invalid_values_and_syncs_the_rest() -> None:
    appliance = make_appliance()
    settings = appliance.commands["settings"].parameters

    sync_command(appliance, "stopProgram", "settings")

    assert float(settings["onOffStatus"].value) == 0
    assert settings["windDirectionVertical"].value == "7"
    assert settings["windDirectionVerticalPositionSequence"].value == "5"


def test_sync_command_ignores_unknown_commands() -> None:
    appliance = make_appliance()
    sync_command(appliance, "missing", "settings")
    sync_command(appliance, "stopProgram", "missing")
    assert float(appliance.commands["settings"].parameters["onOffStatus"].value) == 1


@pytest.mark.asyncio
async def test_ac_turn_off_completes_and_writes_state() -> None:
    appliance = make_appliance()
    entity = object.__new__(HonACClimateEntity)
    entity._device = appliance
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_hvac_mode(HVACMode.OFF)

    appliance.commands["stopProgram"].send.assert_awaited_once()
    assert float(appliance.commands["settings"].parameters["onOffStatus"].value) == 0
    entity.async_write_ha_state.assert_called_once()
