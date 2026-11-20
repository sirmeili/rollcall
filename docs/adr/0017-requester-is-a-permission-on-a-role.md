# Requester is a permission on top of a role, not a fourth role

Requester is a yes/no permission a user holds alongside their role (Viewer, Editor or Admin), never on its own. The archived spec had Requester as a separate role limited to the Catalog and their own requests. It doesn't fit the ranked role ladder, because it can do things a Viewer can't and can't do things a Viewer can. Making it a permission keeps the ladder intact and lets an Editor or Admin also submit requests. With Viewer as the minimum role, every Requester can see the stock they are choosing filament from.

## Consequences

Request routes check the permission and the role separately. A Viewer who is a Requester sees only their own requests, while Editors and Admins see every request. Turning Requester off leaves the user read-only access to the requests they made, except that they can still cancel one that hasn't started printing (#76). They can't edit a request or submit a new one.
