"""Config flow for Appliance Status Monitor."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import CONF_APPLIANCE_NAME, CONF_POWER_ENTITY, DOMAIN


class ApplianceStatusConfigFlow(
    config_entries.ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for Appliance Status Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that the power entity exists
            power_entity = user_input[CONF_POWER_ENTITY]
            state = self.hass.states.get(power_entity)

            if state is None:
                errors[CONF_POWER_ENTITY] = "entity_not_found"
            else:
                # Check for duplicate entries with same power entity
                await self.async_set_unique_id(power_entity)
                self._abort_if_unique_id_configured()

                name = user_input[CONF_APPLIANCE_NAME]
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APPLIANCE_NAME): str,
                    vol.Required(CONF_POWER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="power",
                            multiple=False,
                        ),
                    ),
                }
            ),
            errors=errors,
        )
