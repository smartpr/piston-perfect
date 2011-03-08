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

Make sure to put the following settings in your Django settings module::

   PISTON_IGNORE_DUPE_MODELS = True
   PISTON_FORMATS = 'json',	# Replace with your formats of choice.

:TODO: Examples

.. note::
   The first is an obscure Piston setting that is required to prevent the
   warning in :class:`piston.handler.HandlerMetaClass`, which also crashes if
   the model that it is trying to put into the :dfn:`typemapper` is ``None``.
   This in turn is necessary to prevent the custom handler types that are
   created in :meth:`piston.emitters.Emitter.in_typemapper` from being
   registered in (and messing up) the typemapper.

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
