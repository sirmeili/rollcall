# Print Requests depends on Inventory, never the reverse

RollCall stays one app with two modules. Print Requests reads stock, holds and products from Inventory; Inventory never imports Print Requests, so it keeps working and testing on its own.
