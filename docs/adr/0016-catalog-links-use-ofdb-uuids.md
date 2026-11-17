# Catalog links use OFDB's UUIDs, not a foreign key

A product's catalog link stores its catalog color's OFDB UUID rather than a foreign key to the catalog tables. A catalog sync deletes and reinserts those tables, so a foreign key would break every link on every sync. When OFDB merges colors, a link follows `moved_from` to the new UUID. A manual link to a color that has left the catalog is kept and shown as "No longer in the catalog", so a person can relink or clear it. Automatic links are recomputed after each sync.
