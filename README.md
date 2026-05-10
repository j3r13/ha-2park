# 2Park Home Assistant Integration

Unofficial 2Park integration for Home Assistant.

This integration allows you to control and monitor your 2Park parking sessions directly from Home Assistant.

---

# Features

- Dynamic parking switches
- Start/stop parking actions
- Manual license plate support
- Automatic temporary switch creation for manually entered plates
- Balance sensor
- Last action sensor
- Verification after parking start/stop
- Automatic product/location discovery

---

# Installation

## Install using HACS

1. Open HACS
2. Go to **Integrations**
3. Open the menu (⋮) → **Custom repositories**
4. Add:

```text
https://github.com/j3r13/ha-2park
```

Category:

```text
Integration
```

5. Install **2Park**
6. Restart Home Assistant
7. Go to:

```text
Settings → Devices & Services
```

8. Add the **2Park** integration
9. Enter your:
   - 2Park email address
   - 2Park password

The integration will automatically discover the correct product and parking location in most cases.

---

# Dynamic Switches

Each configured 2Park favorite/member automatically becomes a Home Assistant switch entity.

Example:

```text
switch.2park_john
```

Switch behavior:

- ON → starts parking
- OFF → stops parking

---

# Sensors

## Balance Sensor

Displays the current 2Park parking balance.

Example:

```text
sensor.2park_balance
```

---

## Last Action Sensor

Displays information about the latest parking action.

Includes:
- success state
- verification state
- plate
- message
- action timestamp

Example attributes:

```yaml
success: true
verified: true
plate: XX999X
message: Parking action started
```

---

# Manual License Plate Entry

The integration supports manually entered license plates through the built-in Home Assistant services.

Available services:

- `twopark.start_plate`
- `twopark.stop_plate`
- `twopark.toggle_plate`

These services can be used directly in:
- automations
- scripts
- developer tools
- Assist

---

## Example Service Call

```yaml
action: twopark.start_plate
data:
  plate: RG692Z
```

---

# Dashboard Input (Optional)

If you want to enter license plates directly from a Home Assistant dashboard, create a Home Assistant `input_text` helper.

Go to:

```text
Settings → Devices & Services → Helpers
```

Create a new:

```text
Text Helper
```

Example entity name:

```text
input_text.handmatig_kenteken
```

This helper can then be used together with dashboard buttons, scripts or automations.

---

# Temporary Manual Switches

When manually starting a parking session:

- a temporary switch entity is automatically created
- the switch can be used to stop the parking session
- the temporary switch is automatically removed after the parking session ends

This makes manually entered plates behave the same as normal 2Park favorites.

---

# Important Notes

This integration focuses on:
- parking session control
- parking monitoring
- Home Assistant automation

The following actions must still be managed through the official 2Park environment:

- adding/removing favorites (members)
- parking credit top-ups
- permit management
- account settings
- municipality-specific settings

---

# Disclaimer

This project is unofficial and is not affiliated with 2Park.

Use at your own risk.

Always verify active parking sessions yourself to prevent parking fines.