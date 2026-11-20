Many products are several devices in one: each outlet of a power strip, each channel of a relay board. Home Assistant can only show such parts as separate devices linked to a hub (`via_device_id`), each repeating the hardware details of the whole. We want them to be parts of their device.

## The feature

A device can now be a child device: a logical part of another device, its parent.

**In core.** An integration can declare a device as a child of another device of the same config entry and subentry. A child keeps only what is its own (its identifiers, name, area, labels, whether it is disabled, and its config entry and subentry) and takes everything else, such as manufacturer, model and versions, from its parent. Only one level is allowed: a child cannot be a parent. A device that was registered before as a device of its own becomes a child when its integration declares it so, keeping its id, the name its user gave it and its area. Children are stored with the registry and survive a restart.

- A child without an area of its own is in its parent's area wherever areas count: in area targets of actions, in templates, and in what an area holds.
- Disabling a parent disables its children, which are then disabled because of their device; enabling the parent enables those children again. Children disabled for another reason stay as they are.
- Removing a parent removes its children and their entities; a child whose parent or config entry is gone is cleaned up.
- Targeting a device in an action also targets its children's entities.
- Over the WebSocket API, `config/device_registry/list` returns children beside the other devices, each with only its own fields and the id of its parent; every device says its parent, if any, in `parent_device_id`. A child's name, area, labels and disabled state can be changed with `config/device_registry/update`, as any device's.
- The demo integration's power strip (`kitchen_sink`) now has its two outlets as children.
- Custom integrations that read a device attribute a child does not have keep working for now, with a deprecation warning.

**In the frontend.**

1. The frontend understands the new device list: children are complete devices everywhere in it, with the details they take from their parent, and the new reason a device can be disabled.
2. A child device shows in its parent's area when it has none of its own: on the devices dashboard (area column, grouping and filtering) and on the device page.
3. A device's page lists its child devices, and a child's page links to its parent.
4. On an integration's page, children are nested and indented under their parent.

It is done when it is on `main` of both repositories and works there: Home Assistant starts from a fresh install with the frontend's build, and its owner can disable the demo power strip in its device settings and see both outlets disabled with it, then enable it and see them come back. The tests each repository has today should still pass. Use the names and signatures in each repository's `INTERFACE.md`.
