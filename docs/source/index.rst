piston-perfect
==============

`Django Piston <http://bitbucket.org/jespern/django-piston/>`_ on steroids.
Design inspired by slide 25 of `<http://www.slideshare.net/landlessness/teach-
a-dog-to-rest>`_ and the reality of developing a RESTful web API for `Smart.pr
<http://smart.pr/>`_. Lives in a module named :mod:`piston_perfect` that
functions as a layer on top of :mod:`piston`.

.. TODO: Hyperlink targets are not rendered in Sphinx's text output format.

.. automodule:: piston_perfect
   :members:

You can use the following settings attribute to specify the data formats that
you want your API to support:

   PISTON_FORMATS = 'json',     # Defaults to `'json',`.

:TODO: Examples

:mod:`~piston_perfect.handlers`
-------------------------------

.. autoclass:: piston_perfect.handlers.BaseHandler
   :members:
   :member-order: bysource

.. autoclass:: piston_perfect.handlers.ModelHandler
   :members:
   :undoc-members:
   :member-order: bysource

:mod:`~piston_perfect.authentication`
-------------------------------------

.. autoclass:: piston_perfect.authentication.DjangoAuthentication
   :members:

:mod:`~piston_perfect.resource`
-------------------------------

.. automodule:: piston_perfect.resource
   :members:

:mod:`~piston_perfect.patches`
------------------------------

.. automodule:: piston_perfect.patches
