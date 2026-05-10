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
plate: RG692Z
message: Parking action started
```

---

# Manual License Plate Entry

The integration also supports manually entered license plates.

To use this feature, first create a Home Assistant helper.

---

## Step 1 — Create a Text Helper

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

This helper will be used to enter license plates manually from the Home Assistant UI.

---

## Step 2 — Create a Script

Create a Home Assistant script similar to the following example:

```yaml
sequence:
  - variables:
      plate_value: >
        {{ states('input_text.handmatig_kenteken')
           | trim
           | upper
           | replace('-', '')
           | replace(' ', '') }}

  - condition: template
    value_template: >
      {{ plate_value not in ['', 'unknown', 'unavailable', 'none'] }}

  - action: twopark.start_plate
    data:
      plate: "{{ plate_value }}"

alias: Start 2Park Manual Plate
```

This script:
- reads the helper value
- normalizes the license plate
- starts a parking session using the integration service

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