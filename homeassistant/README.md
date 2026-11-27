# Crema for Home Assistant

A small custom integration that turns a Crema server into sensors: total shots,
this week, today, café visits, average rating / dose / yield / time, beans in
stock, favourite bean, best rating, and when you last pulled a shot.

It polls `GET /api/stats` every five minutes with a **read-only token** — no
login, no cookie, and nothing it can write to.

## Install

Copy the `crema` folder into your Home Assistant config:

```bash
scp -r custom_components/crema <ha-host>:/config/custom_components/
```

Restart Home Assistant, then **Settings → Devices & services → Add integration
→ Crema** and fill in:

| Field | Value |
|---|---|
| URL | where you open Crema, e.g. `http://crema.local:8787` |
| Read token | printed by the command below |

## Minting a token

On the Crema host, from the folder you run Crema from:

```bash
COFFEE_DATA_DIR=/path/to/crema/data python3 app.py --issue-read-token <user id>
```

`COFFEE_DATA_DIR` only needs setting if Crema's database lives outside its own
folder — point it at the directory holding `crema.sqlite3`. The token is printed
once and only its SHA-256 is stored in `app_settings`. Running the command again
replaces the old token, so re-minting is also how you revoke one.

## Sensors

| Entity | Unit | Notes |
|---|---|---|
| `sensor.crema_total_shots` | — | every shot, café visits included |
| `sensor.crema_shots_this_week` | — | last 7 days |
| `sensor.crema_shots_today` | — | from the 14-day series |
| `sensor.crema_cafe_visits` | — | café entries only |
| `sensor.crema_average_rating` | — | 0–5, home shots only |
| `sensor.crema_best_rating` | — | attributes: bean, roaster, method, date |
| `sensor.crema_average_dose` | g | espresso shots |
| `sensor.crema_average_yield` | g | espresso shots |
| `sensor.crema_average_shot_time` | s | espresso shots |
| `sensor.crema_beans_in_stock` | — | unarchived bags |
| `sensor.crema_favourite_bean` | — | attributes: roaster, shot count |
| `sensor.crema_last_shot` | timestamp | attributes: bean, method, rating, dose, yield, time |

`last_shot` is the useful one for automations — "no coffee logged in three
days", or a notification when a new bag gets dialled in.
