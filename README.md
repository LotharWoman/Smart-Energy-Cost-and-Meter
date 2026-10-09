# ⚡ Smart Energy Cost & Meter for Home Assistant

[![Home Assistant Custom Component](https://img.shields.io/badge/Home%20Assistant-Custom%20Component-blue)](https://www.home-assistant.io/)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

🇬🇧 English | 🇩🇪 [Deutsch](https://github.com/LotharWoman/Smart-Energy-Cost-and-Meter/blob/main/README.de.md)

**Smart Energy Cost & Meter** turns **one** energy sensor into up to 16 consumption and cost counters for the Energy dashboard. It does not stop at `kWh × price`: it also adds the pro-rated **base fee** (*Grundgebühr*) of your contract, so the cost sensors show what you actually have to pay.

## 🚀 Key Features

### 💰 Realistic Cost Tracking
- **Fixed or dynamic price:** use a fixed price per kWh, or select a price sensor in €/kWh (e.g. Tibber, including quarter-hourly prices). Every consumption step is priced with the price valid at that moment.
- **Smart fallback:** if the price sensor is unavailable or not numeric, the fixed price is used automatically.
- **Pro-rated base fee:** the daily share (monthly fee ÷ days of that month) is booked once per day at a billing time you choose.

### ⏱ Flexible Time Intervals
For energy (kWh) and cost (EUR) you can enable any of these 8 intervals:
**Total · Yearly · Quarterly · Monthly · Weekly · Daily · Hourly · Quarter-hourly**

Interval sensors start again at 0 at the calendar boundary (weeks start on Monday). The cost sensors report `last_reset`, so Home Assistant statistics treat the reset correctly and never as negative consumption.

### 🛡 Robust Counting
The counters continue from their last known value in all everyday situations:
- **Meter replaced** or counter restarted (new meter starts at 0 or at a very different value): the counters keep going from where they were, nothing is lost or double-counted.
- **Source sensor temporarily unavailable:** consumption during the outage is added once the sensor is back.
- **Home Assistant restart:** values are restored, consumption during the downtime is caught up, and a base fee missed while Home Assistant was off is booked afterwards.
- **Integration removed and re-installed:** values are kept in the integration's own storage (`.storage/smart_energy_cost_and_meter.sensor_values`), independent of the entity registry.
- **Changing the source sensor** in the options (e.g. a new meter with a new entity) keeps all values and just starts with a fresh baseline.

### 🎯 Set Start Values and Corrections
Setting a value in *Developer tools → States* does not work (it is overwritten immediately). Use the action `smart_energy_cost_and_meter.set_value` instead, for any sensor of the integration and at any time (e.g. after reading your real meter).

### 🛠 User-Friendly Configuration
Everything is done in the Home Assistant UI, no YAML required:
- Energy sensor to track (kWh, increasing)
- Fixed price per kWh
- Price sensor (optional, €/kWh)
- Monthly base fee
- Time of day at which the daily base fee is booked
- Which of the 16 sensors to create

## 📉 How the Base Fee Works

```
daily base fee = monthly fee / days in that month
```

Once a day, at the configured billing time, this amount is added to the cost sensors **Total, Yearly, Quarterly, Monthly, Weekly and Daily**. Hourly and quarter-hourly cost sensors contain only energy cost.

$$\text{Cost}_{interval} = \sum (\text{kWh} \times \text{price}) + \sum_{days} \frac{\text{Monthly Base Fee}}{\text{Days in Month}}$$

So your **Daily Cost** sensor reflects not only the electricity used today but also the share of the contract for that day.

## 📸 Gallery
- **Integration Menu:** ![Integration Menu](screenshots/over.jpg)
- **Config Dialog:** ![Configuration](screenshots/action.jpg)
- **Config Dialog:** ![Configuration](screenshots/config.jpg)
- **Entity List:** ![Entities](screenshots/entiti.jpg)

## 🛠 Installation

### Via HACS (Recommended)
1. Open **HACS** → **Integrations**.
2. Click the three dots (top right) → **Custom repositories**.
3. Paste `https://github.com/LotharWoman/Smart-Energy-Cost-and-Meter`
4. Select **Integration** as category → **Add**.
5. Download and **restart Home Assistant**.

### Manual Installation
1. Copy the folder `custom_components/smart_energy_cost_and_meter/` to `/config/custom_components/`.
2. Restart Home Assistant.

Requires Home Assistant 2026.1.0 or newer.

## ⚙️ Setup Guide
1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Smart Energy Cost & Meter**.
3. Configure:
   - **Energy Sensor:** your main meter (must report kWh)
   - **Fixed Price:** your standard price per kWh
   - **Price Sensor:** (optional) a sensor with the current price in €/kWh
   - **Monthly Base Fee:** the monthly base charge of your contract
   - **Billing Time:** time of day at which the daily base fee is booked (e.g. `00:30:00`)
4. Select the sensors (Daily, Monthly, …) you want to create.

The sensors are named e.g. `sensor.smart_energy_total_energy` and `sensor.smart_energy_daily_cost`.

## 🎚 Setting a Start Value

Open **Developer tools → Actions**, choose **Set meter value** (`smart_energy_cost_and_meter.set_value`) and select the sensor:

```yaml
action: smart_energy_cost_and_meter.set_value
target:
  entity_id: sensor.smart_energy_total_energy
data:
  value: 12345.6
```

The value is in kWh for energy sensors and in EUR for cost sensors. It is stored immediately, survives restarts, and counting continues from it.

> **Tip:** Set start values *before* adding the sensors to the Energy dashboard. A jump from 0 to 12345 kWh would otherwise show up as consumption in that hour. If it already happened, correct the outlier under *Developer tools → Statistics*.

## ℹ️ Good to Know
- Only **one instance** of the integration is supported.
- The source sensor is expected to report **kWh**.
- **Meter replacement:** a fall of the source value below 90 % of the last value counts as a counter reset, and the new value is counted as consumption since the reset. A rise of more than 50 kWh between two readings is not counted as consumption (the new value just becomes the new baseline) and is logged as a warning.
- **Clean start:** to restart from 0 after removing the integration, set the values to 0 with `set_value` or delete `.storage/smart_energy_cost_and_meter.sensor_values`.

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
