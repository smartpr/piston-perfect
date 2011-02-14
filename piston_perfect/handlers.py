"""
Generic handlers.
"""

import re
from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, connection
from django.http import HttpResponseGone
from django.conf import settings
from piston import handler, resource
from piston.utils import FormValidationError
from .authentication import Authentication
from .resource import Resource


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
		
		# An inline form definition should never end up on the resulting type
		# as is, but should be assigned to the *form* attribute instead.
		inline_form = attrs.pop('Form', None)
		
		cls = super(BaseHandlerMeta, meta).__new__(meta, name, bases, attrs)
		
		# We always auto-generate (and thus overwrite) *allowed_methods*
		# because the definition of which methods are allowed is now done via
		# *create*, *read*, *update* and *delete* and *allowed_methods* should
		# therefore always reflect their settings.
		cls.allowed_methods = []
		for method, operation in resource.Resource.callmap.iteritems():
			if getattr(cls, operation) is True:
				setattr(cls, operation, getattr(cls, "_%s" % operation))
			if callable(getattr(cls, operation)):
				cls.allowed_methods.append(method)
		cls.allowed_methods = tuple(cls.allowed_methods)
		
		# The general idea is that an attribute with value ``True`` indicates
		# that we want to enable it with its default value.
		
		if cls.request_fields is True:
			cls.request_fields = 'field'
		
		# An inline form always presides over any existing or directly
		# assigned values.
		if inline_form:
			cls.form = inline_form
		
		if cls.order_data is True:
			cls.order_data = 'order'
		
		if cls.slice_data is True:
			cls.slice_data = 'slice'
		
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
	
	
	fields = ()
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
	fields selection by setting this to ``False``.
	
	Multiple fields can be specified by including the parameter multiple
	times: ``?field=id&field=name`` is interpreted as the selection ``('id',
	'name')``.
	"""
	
	exclude = re.compile('^_'),
	"""
	Is used by :meth:`.is_field_allowed` to decide if a field should be
	included in the result. Note that this only applies to scenarios in which
	:attr:`fields` is empty. Should be and iterable of field names and/or
	regular expression patterns. Its default setting is to exclude all field
	names that begin with ``_``.
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
			requested = [field for field in requested if self.is_field_allowed(field)]
		
		return tuple(requested)
	
	def is_field_allowed(self, field):
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
	
	
	model_fields = 'model_key', 'model_type', 'model_description'
	
	@classmethod
	def model_key(cls, model_instance):
		return model_instance.pk
	
	@classmethod
	def model_type(cls, model_instance):
		return model_instance._meta.verbose_name
	
	@classmethod
	def model_description(cls, model_instance):
		return unicode(model_instance)
	
	
	authentication = None
	"""
	The Piston authenticator that should be in effect on this handler. If
	defined as ``True`` (which is not the same as assigning ``True``, as this
	will not work) an instance of :class:`.authentication.Authentication` is
	used. A value of ``None`` implies no authentication, which is the default.
	"""
	
	
	form = None
	"""
	A form class of type :class:`django.forms.Form` that is used to validate
	and clean incoming data (in case of a ``POST`` or ``PUT``). Can be
	``None`` (the default) in which case data is always accepted as is.
	
	An alternative means to the same end is to inline the form definition, in
	which case the name should be capitalized. As such::
	
	  class MyHandler(piston_perfect.handlers.BaseHandler):
	      
	      class Form(django.forms.Form):
	          myfield = django.forms.CharField()
	          def clean(self):
	              return self.cleaned_data
	  
	      # The rest of the handler's definition...
	
	Note that it is possible to use this attribute with other (non-Django)
	form or validator types, but that :meth:`.validate` should be overridden
	to deal with them.
	"""
	
	def validate(self, request, current=None):
		"""
		Uses :attr:`form` to validate and clean incoming data
		(*request.data*). Raises a :exc:`piston.utils.FormValidationError` in
		case of failure. *current*, if given, is the data item that
		*request.data* intends to update.
		"""
		
		# We only know how to deal with instances of *forms.Form*.
		if not forms.Form in getattr(self.form, '__mro__', ()):
			return
		
		# TODO: we could parameterize this behavior.
		if current:
			# Allow for updates using partial data objects.
			request.data.update(current)
		
		form = self.form(request.data)
		if not form.is_valid():
			raise FormValidationError(form)
		
		request.data = form.cleaned_data
	
	
	def data(self, request, *args, **kwargs):
		"""
		Returns the data structure that is being worked on.
		"""
		data = self.data_set(request, *args, **kwargs)
		if data is None:
			data = self.data_item(request, *args, **kwargs)
		return data
	
	def data_set(self, request, *args, **kwargs):
		"""
		Returns the data set that is being worked on.
		"""
		return None
	
	def data_item(self, request, *args, **kwargs):
		"""
		Returns the data item that is being worked on.
		"""
		return HttpResponseGone()
	
	# The *request* parameter in the following methods can be used to
	# construct responses that are structured differently for different types
	# of requests.
	
	# TODO: Deal with scenario in which response is a HttpResponse.
	
	def get_response_data(self, request, response):
		"""
		Reads the data from a response structure.
		"""
		return response.get('data')
	
	def set_response_data(self, request, data, response=None):
		"""
		Sets data onto a response structure. Creates a new response structure
		if none is provided.
		"""
		if response is None:
			response = {}
		response['data'] = data
		return response
	
	
	filter_data = False
	"""
	Filter data query string parameter, or ``True`` if the default
	(``filter``) should be used. Disabled by default.
	"""
	
	def response_filter_data(self, response, request, *args, **kwargs):
		filters = self.filter_data or {}
		
		if not filters:
			return response
		
		data = self.get_response_data(request, response)
		
		for definition, fields in filters.iteritems():
			queries = request.GET.getlist(definition)
			if queries:
				data = self.process_filter_data(data, queries, fields)
		
		self.set_response_data(request, data, response)
		return True
	
	def process_filter_data(self, data, queries, fields):
		raise NotImplementedError
	
	
	order_data = False
	"""
	Order data query string parameter, or ``True`` if the default (``order``)
	should be used. Disabled by default.
	"""
	
	def response_order_data(self, response, request, *args, **kwargs):
		order = request.GET.getlist(self.order_data)
		
		if not order:
			return False
		
		self.set_response_data(request,
			self.process_order_data(
				self.get_response_data(request, response),
				*order
			),
			response,
		)
		return True
	
	def process_order_data(self, data, *order):
		raise NotImplementedError
	
	
	slice_data = False
	"""
	Slice data query string parameter, or ``True`` if the default (``slice``)
	should be used. Disabled by default.
	"""
	
	def response_slice_data(self, response, request, *args, **kwargs):
		slice = request.GET.get(self.slice_data, None)
		
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
			self.process_slice_data(data, *process),
			response,
		)
		return True
	
	def process_slice_data(self, data, start=None, stop=None, step=None):
		try:
			return data[start:stop:step]
		except:
			# Allows us to run *response_slice_data* without having to worry
			# about if the data is actually sliceable.
			return data
	
	
	def POST(self, request, *args, **kwargs):
		self.validate(request)
		return self.set_response_data(request, self.create(request, *args, **kwargs))
	
	def GET(self, request, *args, **kwargs):
		
		# We can simply assume that :attr:`read` is callable here, as we have
		# defined :attr:`allowed_methods` based on the callability of the CRUD
		# operator methods.
		response = self.set_response_data(request, self.read(request, *args, **kwargs))
		
		self.response_filter_data(response, request, *args, **kwargs)
		self.response_order_data(response, request, *args, **kwargs)
		self.response_slice_data(response, request, *args, **kwargs)
		
		return response
	
	def PUT(self, request, *args, **kwargs):
		self.validate(request, current=self.data_item(request, *args, **kwargs))
		return self.set_response_data(request, self.update(request, *args, **kwargs))
	
	def DELETE(self, request, *args, **kwargs):
		
		response = self.set_response_data(request, self.delete(request, *args, **kwargs))
		
		self.response_filter_data(response, request, *args, **kwargs)
		self.response_order_data(response, request, *args, **kwargs)
		self.response_slice_data(response, request, *args, **kwargs)
		
		return response
	
	
	create = False
	def _create(self, request, *args, **kwargs):
		"""
		Implementation that is used for :attr:`create` if it is defined as
		``True``.
		"""
		return request.data
	
	read = False
	def _read(self, request, *args, **kwargs):
		return self.data(request, *args, **kwargs)
	
	update = False
	def _update(self, request, *args, **kwargs):
		return request.data
	
	delete = False
	def _delete(self, request, *args, **kwargs):
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


class ModelHandlerMeta(BaseHandlerMeta):
	"""
	Auto-generates a :class:`django.forms.ModelForm` subtype based on
	:attr:`ModelHandler.model`.
	"""
	
	def __new__(meta, name, bases, attrs):
		# TODO: Things probably go wrong if no model type was provided. We
		# should deal with this scenario.
		
		cls = super(ModelHandlerMeta, meta).__new__(meta, name, bases, attrs)
		
		if not cls.form and cls.model:
			class Form(forms.ModelForm):
				class Meta:
					model = cls.model
					fields = tuple(set(cls.fields).intersection(cls.model._meta.get_all_field_names()))
					exclude = cls.exclude_save
			cls.form = Form
		
		return cls

class ModelHandler(BaseHandler):
	"""
	Provides off-the-shelf CRUD operations on data of a certain model type.
	
	Note that in order to prevent accidental exposure of data that was never
	intended to be public, model data fields will not be included in the
	response if they are not explicitly mentioned in
	:attr:`~BaseHandler.fields`. If it is empty model data will be represented
	in a generic way: key, type and description.
	"""
	
	__metaclass__ = ModelHandlerMeta
	
	
	model = None
	
	exclude_nested = ()
	"""
	A list of field names that should be excluded from the fields selection in
	case of a nested representation; i.e. when the model is contained by
	another model object.
	"""
	
	
	exclude_save = ()
	"""
	A list of field names that should be excluded from the auto-generated form
	(see :class:`ModelHandlerMeta`).
	"""
	
	def validate(self, request, current=None):
		"""
		Overrides :meth:`BaseHandler.validate` to take advantage of the fact
		that there is a good chance that :attr:`~BaseHandler.form` is of type
		:class:`django.forms.ModelForm`. We can work with model objects
		instead of plain data; the resulting value in *request.data* is a
		model instance that can safely be saved to database.
		"""
		
		if not forms.ModelForm in getattr(self.form, '__mro__', ()):
			return super(ModelHandler, self).validate(request, current)
		
		if current:
			# Complement *request.data* with data from *current* in order to
			# support updating with partial data.
			for field in self.form.base_fields.keys():
				request.data.setdefault(field, getattr(current, field))
		
		form = self.form(request.data, instance=current)
		if not form.is_valid():
			raise FormValidationError(form)
		
		request.data = form.save(commit=False)
	
	
	def data(self, request, *args, **kwargs):
		for field in kwargs.keys():
			try:
				if self.model._meta.get_field(field).unique:
					# We found a parameter that identifies a single item, so
					# we assume that singular data was requested.
					return self.data_item(request, *args, **kwargs)
			except:
				# No field named *field* on *self.model*.
				pass
		return self.data_set(request, *args, **kwargs)
	
	def data_set(self, request, *args, **kwargs):
		return self.model.objects.filter(**kwargs)
	
	def data_item(self, request, *args, **kwargs):
		try:
			return self.data_set(request, *args, **kwargs).get(**kwargs)
		except ObjectDoesNotExist:
			return super(ModelHandler, self).data_item(request, *args, **kwargs)
	
	
	def process_filter_data(self, data, queries, fields):
		query = models.Q()
		
		for term in ' '.join(queries).split():
			for field in fields:
				query |= models.Q(**{ '%s__icontains' % field: term })
		
		return data.filter(query)
	
	def process_order_data(self, data, *order):
		return data.order_by(*order)
	
	def response_slice_data(self, response, request, *args, **kwargs):
		data = self.get_response_data(request, response)
		
		if not isinstance(data, models.query.QuerySet):
			return False
		
		response['total'] = data.count()
		
		sliced = super(ModelHandler, self).response_slice_data(response, request, *args, **kwargs)
		
		if not sliced:
			del response['total']
		
		return sliced
	
	
	def _create(self, request, *args, **kwargs):
		request.data.save()
		return super(ModelHandler, self)._create(request, *args, **kwargs)
	
	def _update(self, request, *args, **kwargs):
		request.data.save()
		return super(ModelHandler, self)._update(request, *args, **kwargs)
	
	
	def data_safe_for_delete(self, data):
		data.delete()
		return super(ModelHandler, self).data_safe_for_delete(data)
