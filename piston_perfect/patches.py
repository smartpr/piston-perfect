"""
Custom Piston emitters.

We need a few real hacks into Piston's internal logic, all of which originate
here. "Real hacks" as in; extensions that are kind of like black magic because
they require detailed knowledge of Piston's workings at code level. They
depend on some very specific pieces of Piston code and are therefore likely to
break with future versions of Piston.

The idea is to have all the messy stuff collected in this one module and
isolate it as much as possible from the public-facing interfaces in
:mod:`.handlers`. Hopefully this will allow us to deal with Piston updates
without touching anything beyond this module.
"""


from piston import emitters

# This is a hack into Piston which allows us to explicitly specify the fields
# that we want a response to contain. It works by overriding the `fields`
# property of the emitter instance right before it is being used to construct
# the response data.

# It is assumed that a handler specifies a `fields` and/or a `list_fields`
# property, as it is taken as an outline for the set of fields that are
# allowed to be returned. Also, if no fields are specified on the request we
# fall back onto the specification on the handler. The handler's `exclude`
# property should not be used, at it is not taken into account here.

# It looks like this hack is supported by Piston version `0.2.3rc1`, yet the
# [latest revision](http://bitbucket.org/jespern/django-piston/changeset/
# c4b2d21db51a) breaks it again. We are assuming that this is a regression
# that will be fixed before an official release of `0.2.3rc1`. In the meantime
# we have to work with [revision `e539a104d516`](http://bitbucket.org/jespern/
# django-piston/src/e539a104d516/).


# We want to make sure that we only support formats that we explicitly
# register.
map(emitters.Emitter.unregister, emitters.Emitter.EMITTERS.keys())


def nested_mode(handler):
	if handler:
		# TODO: subclass from handler in order to not lose method fields.
		class PseudoHandler(object):
			fields = '_phantom',
			exclude = handler.exclude_nested	# TODO: Concat handler.exclude(?)
			extra_fields = handler.fields or ('model_key', 'model_type', 'model_description')	# handler in typemap, but empty fields spec
			@classmethod
			def model_key(cls, model_instance):
				return model_instance.pk
			@classmethod
			def model_type(cls, model_instance):
				return model_instance._meta.verbose_name
			@classmethod
			def model_description(cls, model_instance):
				return unicode(model_instance)
	else:
		class PseudoHandler(object):
			fields = 'model_key', 'model_type', 'model_description'		# no handler in type map for the current model type.
			exclude = ()
			@classmethod
			def model_key(cls, model_instance):
				return model_instance.pk
			@classmethod
			def model_type(cls, model_instance):
				return model_instance._meta.verbose_name
			@classmethod
			def model_description(cls, model_instance):
				return unicode(model_instance)
	return PseudoHandler

# # TODO: Move to emitters.
# def apply_requested_fields(request, response):
# 	fields = self.get_requested_fields(request)
# 	
# 	def recursive_apply(data):
# 		if isinstance(data, (list, tuple, set, models.query.QuerySet)):
# 			return map(recursive_apply, data)
# 		
# 		if not hasattr(data, 'items'):
# 			return data
# 		
# 		return dict([(key, value)
# 			for key, value in data.items()
# 			if key in fields or not fields and self.allow_field(key)])
# 	
# 	return self.set_response_data(request, response,
# 		recursive_apply(self.get_response_data(request, response)))
# 

from django.db import models

class JsonEmitter(emitters.JSONEmitter):
	"""
	JSON emitter. We cannot simply use Piston's implementation because
	emitters are the only object type for which a new instance is created at
	every HTTP request. We need it to hook in some request-level Piston
	tweaks.
	"""
	
	def __init__(self, *args, **kwargs):
		# TODO: Move to handler.
		from django.db import connection
		# connection.queries = []
		return super(JsonEmitter, self).__init__(*args, **kwargs)
	
	def construct(self):
		constructed = self.handler.post_construct(self._request, self.data, super(JsonEmitter, self).construct())
		del self._request
		return constructed
	
	def render(self, request):
		from .handlers import ModelHandler
		if isinstance(self.handler, ModelHandler):
			self.fields = self.handler.get_requested_fields(request)
		else:
			self.fields = ()
			fields = self.handler.get_requested_fields(request)
			def recursive_apply(data):
				if isinstance(data, (list, tuple, set, models.query.QuerySet)):
					return map(recursive_apply, data)

				if not hasattr(data, 'items'):
					return data

				return dict([(key, value)
					for key, value in data.items()
					if key in fields or not fields and self.handler.is_field_allowed(key)])
			self.handler.set_response_data(request, self.data,
				recursive_apply(self.handler.get_response_data(request, self.data)))
		
		# self.fields = self.handler.get_emitter_fields(request)
		# TODO: Don't run apply_requested_fields if self.data is a HttpResponse
		# self.data = self.handler.apply_requested_fields(request, self.data)
		self._request = request
		rendered = super(JsonEmitter, self).render(request)
		return rendered
	
	def in_typemapper(self, *args, **kwargs):
		# Is executed every time the emitter encounters model data for which
		# no fields spec is known to the emitter -- it will try to find a
		# corresponding handler (and fields spec) via this method.
		return nested_mode(super(JsonEmitter, self).in_typemapper(*args, **kwargs))
