"""
Generic handlers.
"""

import re
from django import forms
from django.db import models, connection
from django.conf import settings
from piston import handler, resource
from .authentication import Authentication
from .resource import Resource
from .utils import MethodNotAllowed


class BaseHandlerMeta(handler.HandlerMetaClass):
	"""
	Allows a handler class definition to be different from a handler class
	type. This is useful because it enables us to set attributes to default
	values without requiring an explicit value in their definition. See for
	example :attr:`BaseHandler.request_fields`.
	
	Note that this inherits from :mod:`piston.handler.HandlerMetaClass`, which
	deals with some model related stuff. This is not a problem for non-model
	handlers as long as they do not have a ``model`` attribute with a value
	other than ``None`` (which :class:`BaseHandler` doesn't).
	"""
	
	def __new__(meta, name, bases, attrs):
		
		# Operations should not be allowed unless explicitly enabled. At the
		# same time we want to be able to define inheritable default
		# implementations of *create*, *read*, *update* and *delete*. We marry
		# the two requirements by disabling operations (overriding them with
		# ``False``) at the last minute, just before the class is being
		# constructed.
		for operation in resource.Resource.callmap.values():
			attrs.setdefault(operation, False)
			if attrs.get(operation) is True:
				del attrs[operation]
		
		cls = super(BaseHandlerMeta, meta).__new__(meta, name, bases, attrs)
		
		# We always auto-generate (and thus overwrite) *allowed_methods*
		# because the definition of which methods are allowed is now done via
		# *create*, *read*, *update* and *delete* and *allowed_methods* should
		# therefore always reflect their settings.
		cls.allowed_methods = tuple([method
			for method, operation in resource.Resource.callmap.iteritems()
			if callable(getattr(cls, operation))])
		
		# The general idea is that an attribute with value ``True`` indicates
		# that we want to enable it with its default value.
		
		if cls.request_fields is True:
			cls.request_fields = 'field'
		
		if cls.order is True:
			cls.order = 'order'
		
		if cls.slice is True:
			cls.slice = 'slice'
		
		# Changing this attribute at run-time won't work, but removing the
		# attribute for that reason is not a good idea, as that would render
		# the resulting handler type unsuited for further inheritance.
		if cls.authentication is True:
			cls.authentication = Authentication()
		
		cls.resource = Resource(cls, authentication=cls.authentication)
		
		return cls

class BaseHandler(handler.BaseHandler):
	"""
	All handlers should (directly or indirectly) inherit from this one. Its
	public attributes and methods were devised with extensibility in mind, so
	don't hesitate to override.
	
	.. note::
	   Piston's :attr:`piston.handler.BaseHandler.allowed_methods` attribute
	   should not be used, as it is auto-generated based on the values of
	   :attr:`.create`, :attr:`.read`, :attr:`.update` and :attr:`.delete`.
	"""
	
	__metaclass__ = BaseHandlerMeta
	
	
	fields = ()	# TODO: Document that this field also has meaning for saving data => empty means no data will be accepted
	"""
	Specifies the fields that are allowed to be included in a response. It
	also serves as the set of options for request-level fields selection (see
	:attr:`request_fields`). If it is an empty iterable (the default) the
	decision whether or not a field is allowed to be included is taken by
	:meth:`.is_field_allowed`.
	
	Note that the value of this attribute is not automatically used as field
	definition on the emitter, as is the behavior of Piston's default base
	handler. See the monkey-patched :meth:`piston.emitters.Emitter.construct`
	in :mod:`.patches` for more information.
	"""
	
	request_fields = True
	"""
	Determines if request-level fields selection is enabled. Should be the
	name of the query string parameter in which the selection can be found.
	If this attribute is defined as ``True`` (which is the default) the
	default parameter name ``field`` will be used. Note that setting to (as
	opposed to "defining as") ``True`` will not work. Disable request-level
	fields selection by defining this as ``False``.
	
	Multiple fields can be specified by including the parameter multiple
	times: ``?field=id&field=name`` is interpreted as the selection ``('id',
	'name')``.
	"""
	
	exclude = re.compile('^_'),
	"""
	Is used by :meth:`.is_field_allowed` to decide if a field should be
	included in the result. Note that this only applies to scenarios in which
	:attr:`fields` is empty. Should be an iterable of field names and/or
	regular expression patterns. Its default setting is to exclude all field
	names that begin with ``_``.
	"""
	
	exclude_in = ()
	"""
	A list of field names that will be filtered out of incoming data. Fields
	that are not listed in :attr:`.fields` will never be considered either, so
	this attribute should contain field names that are also in
	:attr:`.fields`. Is used by :meth:`.may_input_field`.
	"""
	
	def get_requested_fields(self, request):
		"""
		Returns the fields selection for this specific request. Takes into
		account the settings for :attr:`.fields` and :attr:`.request_fields`,
		and the query string in *request*. Returns ``()`` in case no
		selection has been specified in any way.
		"""
		
		# Gets the fields selection as specified in the query string if
		# enabled and provided, and an empty list in all other scenarios.
		requested = request.GET.getlist(self.request_fields)
		
		if self.fields:
			if requested:
				requested = set(requested).intersection(self.fields)
			else:
				requested = self.fields
		else:
			# We have no handler-level fields specification to set off the
			# request-level fields specification against, so let
			# *self.is_field_allowed* decide if a field should be included.
			requested = [field for field in requested if self.may_output_field(field)]
		
		return tuple(requested)
	
	def may_output_field(self, field):
		"""
		Determines if the field named *field* should be included in the
		response. Returns ``False`` for any field that matches the
		specification in :attr:`exclude`, ``True`` otherwise. Note that this
		method will not be consulted if :attr:`fields` is non-empty.
		"""
		
		for exclude in self.exclude:
			if isinstance(exclude, basestring):
				if exclude == field:
					return False
			else:
				# Anything that is not a string is assumed to be a regular
				# expression pattern.
				if exclude.match(field):
					return False
		return True
	
	def may_input_field(self, field):
		"""
		Decides if a field should be filtered out of incoming data.
		"""
		
		if self.fields:
			return field in set(self.fields) - set(self.exclude_in)
		
		return not field in self.exclude_in
	
	
	model_fields = 'model_key', 'model_type', 'model_description'
	
	@classmethod
	def model_key(cls, instance):
		return instance.pk
	
	@classmethod
	def model_type(cls, instance):
		return instance._meta.verbose_name
	
	@classmethod
	def model_description(cls, instance):
		return unicode(instance)
	
	
	authentication = None
	"""
	The Piston authenticator that should be in effect on this handler. If
	defined as ``True`` (which is not the same as assigning ``True``, as this
	will not work) an instance of :class:`.authentication.Authentication` is
	used. A value of ``None`` implies no authentication, which is the default.
	"""
	
	
	def validate(self, request, *args, **kwargs):
		if not request.data:
			if request.method.upper() == 'POST':
				raise ValidationError("No data provided.")
			return
		
		request.data = dict([(field, value)
			for field, value in request.data.iteritems()
			if self.may_input_field(field)])
		
		return
	
	
	def working_set(self, request, *args, **kwargs):
		"""
		Returns the operation's base data set. No data beyond this set will be
		accessed or modified.
		"""
		
		raise NotImplementedError
	
	def data_set(self, request, *args, **kwargs):
		
		data = self.working_set(request, *args, **kwargs)
		
		filters = self.filters or {}
		if filters:
			for name, definition in filters.iteritems():
				values = request.GET.getlist(name)
				if values:
					data = self.filter_data(data, definition, values)
		
		order = request.GET.getlist(self.order)
		if order:
			data = self.order_data(data, *order)
		
		return data
	
	def data_item(self, request, *args, **kwargs):
		"""
		Returns the data item that is being worked on.
		"""
		return None
	
	def data(self, request, *args, **kwargs):
		data = self.data_item(request, *args, **kwargs)

		if data is None:
			data = self.data_set(request, *args, **kwargs)

		return data
	
	
	# The *request* parameter in the following methods can be used to
	# construct responses that are structured differently for different types
	# of requests.
	
	# TODO: Deal with scenario in which response is a HttpResponse.
	
	def get_response_data(self, request, response):
		"""
		Reads the data from a response structure. Raises a *KeyError* if
		response contains no data.
		"""
		return response['data']
	
	def set_response_data(self, request, data, response=None):
		"""
		Sets data onto a response structure. Creates a new response structure
		if none is provided.
		"""
		if response is None:
			response = {}
		response['data'] = data
		return response
	
	
	filters = False
	"""
	Filter data query string parameter, or ``True`` if the default
	(``filter``) should be used. Disabled by default.
	"""
	
	def filter_data(self, data, definition, values):
		return data
	
	
	order = False
	"""
	Order data query string parameter, or ``True`` if the default (``order``)
	should be used. Disabled by default.
	"""
	
	def order_data(self, data, *order):
		return data
	
	
	slice = False
	"""
	Slice data query string parameter, or ``True`` if the default (``slice``)
	should be used. Disabled by default.
	"""
	
	def response_slice_data(self, response, request, *args, **kwargs):
		slice = request.GET.get(self.slice, None)
		
		if not slice:
			return False
		
		data = self.get_response_data(request, response)
		
		# Allow this to be preempted by other methods, which may be useful (or
		# necessary) in case of big lazy loading data sets.
		if not 'total' in response:
			response['total'] = len(data)
		
		slice = slice.split(':')
		
		process = []
		for i in range(3):
			try:
				slice_arg = slice[i]
			except IndexError:
				slice_arg = None
			try:
				# A slice argument is usually a number...
				process.append(int(slice_arg))
			except:
				# ... but don't choke if it's not.
				process.append(slice_arg or None)
		
		self.set_response_data(request,
			self.slice_data(data, *process),
			response,
		)
		return True
	
	def slice_data(self, data, start=None, stop=None, step=None):
		try:
			return data[start:stop:step]
		except:
			# Allows us to run *response_slice_data* without having to worry
			# about if the data is actually sliceable.
			return data
	
	
	def request(self, request, *args, **kwargs):
		if request.method.upper() == 'POST' and not self.data_item(request, *args, **kwargs) is None:
			raise MethodNotAllowed('GET', 'PUT', 'DELETE')
		
		if hasattr(request, 'data'):
			self.validate(request, *args, **kwargs)
		
		response = self.set_response_data(request,
			getattr(self, resource.Resource.callmap.get(request.method.upper()))(request, *args, **kwargs))
		
		# Slicing should be done after everything else, as it is to be
		# perceived as a "view on the data set in the response," rather than
		# a selection mechanism to influence the data that the requested
		# operation should work with.
		self.response_slice_data(response, request, *args, **kwargs)
		
		return response
	
	def create(self, request, *args, **kwargs):
		return request.data
	
	def read(self, request, *args, **kwargs):
		return self.data(request, *args, **kwargs)
	
	def update(self, request, *args, **kwargs):
		# If *request.data* is not an appropriate response, we should *make*
		# it an appropriate response. Never directly use *self.data*, as that
		# is not the result of an update operation.
		return request.data
	
	def delete(self, request, *args, **kwargs):
		return self.data(request, *args, **kwargs)
	
	
	def response_add_debug(self, response, request):
		# Unfortunately we lost *args*/*kwargs* in *response_constructed*.
		response['debug'] = dict(
			query_log=connection.queries,
			query_count=len(connection.queries),
		)
		return response
	
	def response_constructed(self, response, unconstructed, request):
		if request.method.upper() == 'DELETE':
			self.data_safe_for_delete(self.get_response_data(request, unconstructed))
		
		if settings.DEBUG:
			response = self.response_add_debug(response, request)
		
		return response
	
	def data_safe_for_delete(self, data):
		pass


class ModelHandler(BaseHandler):
	"""
	Provides off-the-shelf CRUD operations on data of a certain model type.
	
	Note that in order to prevent accidental exposure of data that was never
	intended to be public, model data fields will not be included in the
	response if they are not explicitly mentioned in
	:attr:`~BaseHandler.fields`. If it is empty model data will be represented
	in a generic way: key, type and description.
	"""
	
	model = None
	"""
	A model class of type :class:`django.db.models.Model`.
	"""
	
	
	exclude_nested = ()
	"""
	A list of field names that should be excluded from the fields selection in
	case of a nested representation; i.e. when the model is contained by
	another model object.
	"""
	
	
	def may_input_field(self, field):
		result = super(ModelHandler, self).may_input_field(field)
		
		if not result:
			result
		
		try:
			return not self.model._meta.get_field(field, many_to_many=False).primary_key
		except models.FieldDoesNotExist:
			return False
			
	
	def validate(self, request, *args, **kwargs):
		super(ModelHandler, self).validate(request, *args, **kwargs)
		
		if not request.data:
			return
		
		if request.method.upper() == 'POST':
			request.data = self.model(**request.data)
		
		if request.method.upper() == 'PUT':
			current = self.data(request, *args, **kwargs)
			
			def update(current, data):
				if not isinstance(current, self.model):
					map(update, current, [data] * len(current))
				for field, value in data.iteritems():
					# TODO: Should we anticipate on errors here?
					setattr(current, field, value)
			
			update(current, request.data)
			
			request.data = current
	
	
	def working_set(self, request, *args, **kwargs):
		return self.model.objects.filter(**kwargs)
	
	def data_item(self, request, *args, **kwargs):
		# First we check if we have been provided with conditions that are
		# capable of denoting a single item. If we would try to ``get`` an
		# instance based on *kwargs* right away, things would go wrong in case
		# of a set with one element. This element would be returned by this
		# method as if it was explicitly requested.
		for field in kwargs.keys():
			try:
				if self.model._meta.get_field(field).unique:
					# We found a parameter that identifies a single item, so
					# we assume that singular data was requested. If the data
					# turns out not to be there, the raised exception will
					# automatically be handled by the error handler in
					# Resource.
					return self.working_set(request, *args, **kwargs).get(**{ field: kwargs.get(field) })
			except models.FieldDoesNotExist:
				# No field named *field* on *self.model*, try next field.
				pass
		return super(ModelHandler, self).data_item(request, *args, **kwargs)
	
	def filter_data(self, data, definition, values):
		
		if isinstance(definition, basestring):
			return data.filter(**{ definition: values })
		
		if isinstance(definition, (list, tuple)):
			query = models.Q()
		
			for term in ' '.join(values).split():
				for field in definition:
					query |= models.Q(**{ '%s__icontains' % field: term })
			
			return data.filter(query)
		
		return data
	
	def order_data(self, data, *order):
		return data.order_by(*order)
	
	def response_slice_data(self, response, request, *args, **kwargs):
		data = self.get_response_data(request, response)
		
		# Optimization for lazy and potentially large query sets.
		if isinstance(data, models.query.QuerySet) and self.slice in request.GET:
			response['total'] = data.count()
		
		sliced = super(ModelHandler, self).response_slice_data(response, request, *args, **kwargs)
		
		if not sliced and 'total' in response:
			del response['total']
		
		return sliced
	
	
	def create(self, request, *args, **kwargs):
		# The *force_insert* should not be necessary here, but look at it as
		# the ultimate guarantee that we are not messing with existing
		# records.
		try:
			request.data.save(force_insert=True)
		except:
			# Not sure what errors we could get, but I think it's safe to just
			# assume that *any* error means that no record has been created.
			request.data = None
		
		return super(ModelHandler, self).create(request, *args, **kwargs)
	
	read = True
	
	def update(self, request, *args, **kwargs):
		def persist(instance):
			try:
				instance.save(force_update=True)
				return instance
			except:
				return None
		
		if isinstance(request.data, self.model):
			request.data = persist(request.data)
		elif request.data:
			request.data = [instance for instance in request.data if persist(instance)]
		
		return super(ModelHandler, self).update(request, *args, **kwargs)
	
	delete = True
	
	
	def data_safe_for_delete(self, data):
		data.delete()
		return super(ModelHandler, self).data_safe_for_delete(data)
