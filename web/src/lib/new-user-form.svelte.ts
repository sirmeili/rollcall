/** Whether the Users page's new-user form is open. Shared so that the phone bar's New user
 * button can open the form on the page. */
class NewUserFormState {
  open = $state(false);
}

export const newUserForm = new NewUserFormState();
