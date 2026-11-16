# BAMBU_KDF_SALT is a published constant, not a secret we generate

The tag keys are derived with a key-derivation constant that is already public. It is still a setting, kept out of logs, but it is never generated: `ft-sim check-salt` confirms the value in use by re-deriving the keys stored in saved dumps. The server hands it to paired devices for on-phone decoding.
