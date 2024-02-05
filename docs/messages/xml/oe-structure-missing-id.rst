xml-oe-structure-missing-id
###########################
This message is generated whenever a tag having :code:`oe_structure` as one of its classes is missing a valid
:code:`id`. A valid :code:`id` must contain :code:`oe_structure` inside it. So :code:`id="my_unique_id"` is not valid,
while :code:`id="oe_structure_my_unique_id"` is valid.

Rationale
*********
The check was suggested in `this issue <https://github.com/OCA/odoo-pre-commit-hooks/issues/27>`_. Tags with
:code:`oe_structure` as their class are meant for users to edit them through the website builder. If the tag has no
:code:`id`, the website will replace the entire original view with a copy that contains the user changes.
This means updates to other parts of the view (through code, AKA updating a module) may not be reflected.

By providing a valid :code:`id`, only the tag with it will be replaced. Internally Odoo will inherit the original view
and use an XPath to replace the tag with the user's content. This means the rest of the view can still be updated
and changes should be reflected.

Fixing your code
****************
To fix your code you should first of all determine whether the content inside the offending tag should be
editable by users. If it shouldn't, removing :code:`oe_structure` is probably the best solution.

If the content is meant to be edited by users then provide a valid, **unique** ID. In order to avoid collisions
it is often recommended for the ID to contain the template's ID in it. For example:

.. code-block:: xml

  <template id="customer_template_blue" name="Blue Customer Template">
    <main>
      Some stuff that should not be edited
    </main>
    <div class="oe_structure" id="oe_structure_customer_template_blue_greeting">
      <span>Customize this greeting through the website editor!</span>
    </div>
  </template>

Additionally **ensure your code does not depend on any elements inside tags with oe_structure**. User editable
content is volatile and subject to changes or complete removal (if the user so wishes), so something like an
XPath expression may break if the user removes elements referenced in it.
