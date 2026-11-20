# What the hidden tests rely on

The work is judged by the project's own tests, which you cannot see. They use the names below. Each must
exist at exactly this place under exactly this name, declared as shown (every parameter and property), or
the tests that use it cannot run. This says where things live and what they are called, not what they do.

## Names that do not exist yet

### `homeassistant.helpers.device_registry`
- `ChildDeviceEntry`: `class ChildDeviceEntry(BaseDeviceEntry)`
- `ChildDeviceRegistryItems`: `class ChildDeviceRegistryItems(BaseRegistryItems[ChildDeviceEntry])`
- `_CHILD_DEVICE_COMPAT_ATTRS`: `_CHILD_DEVICE_COMPAT_ATTRS = ...`
- `async_child_entries_for_config_entry`: `def async_child_entries_for_config_entry(registry: DeviceRegistry, config_entry_id: str)`
- `async_entries_for_parent_device`: `def async_entries_for_parent_device(registry: DeviceRegistry, parent_device_id: str)`
- `async_get_effective_area_id`: `def async_get_effective_area_id(hass: HomeAssistant, device: AnyDeviceEntry)`

### `homeassistant.helpers.entity_registry`
- `async_get_effective_area_id`: `def async_get_effective_area_id(hass: HomeAssistant, entry: RegistryEntry)`

## Names that exist and whose declaration changes

### `homeassistant.helpers.device_registry`
- `DeviceEntry`: `class DeviceEntry(BaseDeviceEntry)`
