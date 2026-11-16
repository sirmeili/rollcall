# The printer link is direct, read-only MQTT with a pinned certificate

The server connects straight to each printer's LAN MQTT broker, reads reports only, and pins the printer's self-signed certificate on first use. Controlling the printer would need Developer Mode, which isn't planned. If the printer's connection limit is ever hit, an MQTT proxy (`bradsjm/bambu-mqtt-proxy` first) runs as a separate project, not inside RollCall.
