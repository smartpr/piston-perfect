"""
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

from django.db import models
from django.http import HttpResponse
from django.conf import settings
from piston.emitters import Emitter
from .handlers import ModelHandler


# These are all the natively supported formats, including their emitter class
# and content type. Save for later reference.
ALL_FORMATS = Emitter.EMITTERS.copy()

# Reset registered emitters, because we want to enforce making supported
# formats explicit. Also, we want to be able to monkey-patch
# *Emitter.register* before the first registration is done. Because Piston's
# emitter registrations cannot be prevented when importing *Emitter*, the only
# way to achieve our goal is to postpone the moment of first registration.
Emitter.EMITTERS.clear()


# Monkey-patch *Emitter.in_typemapper*.

native_in_typemapper = Emitter.in_typemapper

def in_typemapper(self, *args, **kwargs):
	"""
	Is called by :meth:`piston.emitters.Emitter.construct` when it encounters
	model data and no fields specification is readily available (in
	:attr:`piston.emitters.Emitter.fields`). This can be the case in two
	scenarios:
	
	1. the model data is nested, i.e. referred to by another model instance;
	2. the current handler is not a model handler.
	
	This monkey-patch is needed to be able to alter Piston's default
	behavior for these scenarios:
	
	1. replace the model type handler's fields specification with a nested
	   data specification (see :attr:`.handlers.ModelHandler.exclude_nested`),
	   or with the handler's fallback model representation
	   (:attr:`.handlers.BaseHandler.model_fields`);
	2. prevent Piston from trying to introspect all the fields in the model
	   data (which is risky because it might very well result in a huge chunk
	   of uncurated data ending up in the response) by putting the handler's
	   fallback model representation in place.
	"""
	
	# Try to find a handler for the provided model type.
	handler = native_in_typemapper(self, *args, **kwargs)
	
	# If we have a type handler we might be able to construct a nested fields
	# selection (but only if the handler's *fields* attribute is not empty).
	nested = ()
	if handler:
		nested = tuple(set(handler.fields) - set(handler.exclude_nested))
	
	handler = handler or type(self.handler)
	
	class Handler(handler):
		# If we have no nested fields specification we fall back to the
		# handler's default model representation.
		fields = nested or handler.model_fields
		exclude = ()
		# Prevent this handler from ending up in (and messing up) the
		# typemapper.
		model = None
	
	return Handler

Emitter.in_typemapper = in_typemapper


# Monkey-patch *Emitter.construct*.

native_construct = Emitter.construct

def construct(self):
	"""
	Allows for some stuff to be done right before and right after the response
	is being constructed by the emitter:
	
	* fields selection is taken care of right before construction;
	* a post-construction hook is invoked right after construction in order to
	  give the handler the opportunity to make some last-minute modifications
	  or to perform operations that modify the (unconstructed) data (like
	  removing the data from database).
	"""
	
	# Tell the emitter to not bother with fields selection unless we
	# explicitly instruct it to do otherwise.
	self.fields = ()
	
	try:
		data = self.handler.get_response_data(self.request, self.data)
	except KeyError:
		# No data to be found on the response (probably because we are dealing
		# with an error response), so don't bother with the fields selection
		# and post-construction hook.
		return native_construct(self)
	
	# Before actual construction takes place we have to deal with fields
	# selection.
	
	fields = self.handler.get_requested_fields(self.request)
	
	if isinstance(self.handler, ModelHandler):
		# If we are dealing with a model handler, we can simply delegate
		# field selection to the emitter.
		self.fields = fields

	else:
		# Else we need to do the fields selection ourselves, as Piston's
		# emitter doesn't do fields selection on non-model data.
		
		def process_requested_fields(data):
			if isinstance(data, (list, tuple, set, models.query.QuerySet)):
				return map(process_requested_fields, data)
			
			# We make the assumption that an *items* attribute indicates that
			# we can look for fields.
			if not hasattr(data, 'items'):
				return data
			
			return dict([(field, value)
				for field, value in data.items()
				if field in fields or not fields and self.handler.may_output_field(field)])
		
		# Update the to-be-constructed response in *this.data* with the
		# fields-selected data.
		self.handler.set_response_data(self.request,
			process_requested_fields(data),
			self.data
		)
	
	# Invokes a post-construction hook on the handler whose return value is
	# the definitive response ready for serialization.
	return self.handler.response_constructed(native_construct(self), self.data, self.request)

Emitter.construct = construct


# Monkey-patch *Emitter.register*.

native_register = Emitter.register

def register(cls, name, klass, content_type='text/plain'):
	"""
	We need to monkey-patch this method in order to be able to monkey-patch
	:meth:`piston.emitters.Emitter.render`, as the latter has got no
	implementation and is not being invoked by its inheritors.
	"""
	
	native_render = klass.render

	def render(self, request):
		"""
		We need *request* in (our monkey-patched)
		:meth:`piston.emitters.Emitter.construct`, and this method is the only
		instance method on the emitter that is being invoked with a *request*
		argument.
		"""
		if isinstance(self.data, HttpResponse):
			return self.data
		
		self.request = request
		return native_render(self, request)
	
	klass.render = render
	
	return native_register(name, klass, content_type)

Emitter.register = classmethod(register)


# Register response formats. Is guaranteed to use the monkey-patched
# *Emitter.register*, which means the registered emitter type classes will be
# fully monkey-patched as well.
for format in set(getattr(settings, 'PISTON_FORMATS', ('json', ))).intersection(ALL_FORMATS.keys()):
	Emitter.register(format, *ALL_FORMATS.get(format))
