# The prototype's buttons use a resistor ladder on GPIO35

The three buttons on the CYD prototype share one analog pin (GPIO35) through a resistor ladder, because the CYD has few free pins, the voltages are well separated, and it needs no extra chip. A PCF8574 I/O expander is the fallback. The custom PCB (v2) gives each button its own input instead.
