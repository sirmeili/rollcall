# Android allows plain HTTP; pairing enforces LAN addresses

Android's network security config cannot express "private address ranges only", so the app allows plain HTTP in general and the app itself refuses to pair with an address that is not on the LAN. Pairing with the proxy's HTTPS address is still recommended, since signing in over plain HTTP needs `COOKIE_SECURE=false`.
