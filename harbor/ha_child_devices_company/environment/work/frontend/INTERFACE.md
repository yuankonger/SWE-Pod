# What the hidden tests rely on

The work is judged by the project's own tests, which you cannot see. They use the names below. Each must
exist at exactly this place under exactly this name, declared as shown (every parameter and property), or
the tests that use it cannot run. This says where things live and what they are called, not what they do.

## Names that do not exist yet

### `src/data/device/device_registry.ts`
- `ChildDeviceRegistryEntry`: `export interface ChildDeviceRegistryEntry extends RegistryEntry { id: string; config_entry_id: string; config_subentry_id: string | null; identifiers: [string, string][]; name: string | null; name_by_user: string | null; labels: string[]; area_id: string | null; disabled_by: DeviceDisabler | null; parent_device_id: string; }`
- `devicesInEffectiveArea`: `export const devicesInEffectiveArea = ( devices: Record<string, DeviceRegistryEntry>, areaId: string ): DeviceRegistryEntry[] => ... ; export interface DeviceRegistryEntry extends RegistryEntry { id: string; config_entries: string[]; config_entries_subentries: Record<string, (string | null)[]>; connections: [string, string][]; identifiers: [string, string][]; manufacturer: string | null; model: string | null; model_id: string | null; name: string | null; labels: string[]; sw_version: string | null; hw_version: string | null; serial_number: string | null; via_device_id: string | null; area_id: string | null; name_by_user: string | null; entry_type: "service" | null; disabled_by: DeviceDisabler | null; configuration_url: string | null; primary_config_entry: string | null; parent_device_id: string | null; }`

### `src/data/ws-device_registry.ts`
- `resolveChildDevices`: `export const resolveChildDevices = ( entries: DeviceRegistryListEntry[] ): DeviceRegistryEntry[] => ...`

## Names that exist and whose declaration changes

### `src/common/entity/context/get_device_context.ts`
- `getDeviceArea`: `export const getDeviceArea = ( device: DeviceRegistryEntry, areas: HomeAssistant["areas"], devices: HomeAssistant["devices"] ): AreaRegistryEntry | undefined => ...`

### `src/data/device/device_registry.ts`
- `DeviceRegistryEntry`: `export interface DeviceRegistryEntry extends RegistryEntry { id: string; config_entries: string[]; config_entries_subentries: Record<string, (string | null)[]>; connections: [string, string][]; identifiers: [string, string][]; manufacturer: string | null; model: string | null; model_id: string | null; name: string | null; labels: string[]; sw_version: string | null; hw_version: string | null; serial_number: string | null; via_device_id: string | null; area_id: string | null; name_by_user: string | null; entry_type: "service" | null; disabled_by: DeviceDisabler | null; configuration_url: string | null; primary_config_entry: string | null; parent_device_id: string | null; }`
