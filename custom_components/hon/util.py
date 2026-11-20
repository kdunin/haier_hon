import logging
from contextlib import suppress

from pyhon.appliance import HonAppliance

from .typedefs import HonEntityDescription, HonOptionEntityDescription, T

_LOGGER = logging.getLogger(__name__)


def unique_entities(
    base_entities: tuple[T, ...],
    new_entities: tuple[T, ...],
) -> tuple[T, ...]:
    result = list(base_entities)
    existing_entities = [entity.key for entity in base_entities]
    entity: HonEntityDescription
    for entity in new_entities:
        if entity.key not in existing_entities:
            result.append(entity)
    return tuple(result)


def get_readable(
    description: HonOptionEntityDescription, value: float | str
) -> float | str:
    if description.option_list is not None:
        with suppress(ValueError):
            return description.option_list.get(int(value), value)
    return value


def sync_command(device: HonAppliance, main: str, target: str) -> None:
    """Copy parameter values from command `main` to command `target`.

    Same as `HonAppliance.sync_command(main, target)`, except that a value the
    target parameter does not accept is skipped instead of raising.

    Some appliances ship command defaults outside their own allowed values,
    e.g. an AC `stopProgram` with `windDirectionVerticalPositionSequence: 0`
    while only 2-8 are allowed. pyhon raised a ValueError on that parameter,
    which failed the service call after the command had already been sent and
    left the remaining parameters unsynced.
    """
    base = device.commands.get(main)
    command = device.commands.get(target)
    if not base or not command:
        return
    for name, target_param in command.parameters.items():
        if not (base_param := base.parameters.get(name)):
            continue
        try:
            device.sync_parameter(base_param, target_param)
        except ValueError as error:
            _LOGGER.debug(
                "Skip syncing %s from %s to %s: %s", name, main, target, error
            )
