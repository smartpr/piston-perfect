"""
Generic handlers.
"""


import re
from django import forms
from django.core.exceptions import FieldError, MultipleObjectsReturned
from django.db import models, connection
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed, HttpResponseGone
from django.conf import settings
from piston import handler, resource, emitters
from piston.utils import FormValidationError
from .authentication import Authentication
from .resource import Resource


class BaseHandlerMeta(handler.HandlerMetaClass):
	"""
	Allows a handler class definition to be different from a handler class
	type. This is useful because it enables us to set attributes to default
	values without requiring an explicit value in their definition. See for
	example :attr:`BaseHandler.allowed_methods`.
	
	Note that this inherits from :mod:`piston.handler.HandlerMetaClass`, which
	deals with some model related stuff. This is not a problem for non-model
	handlers as long as they do not have a ``model`` attribute (which
	:class:`BaseHandler` doesn't).
	"""
	
	def __new__(meta, name, bases, attrs):
		
		inline_form = attrs.pop('Form', None)
		
		cls = super(BaseHandlerMeta, meta).__new__(meta, name, bases, attrs)
		
		# The general idea is that an attribute with value ``True`` indicates
		# that we want to enable it with its default value.
		
		if cls.allowed_methods is True:
			cls.allowed_methods = [method
				for method, operation in resource.Resource.callmap.iteritems()
				if getattr(cls, operation, False)]
		
		if cls.request_fields is True:
			cls.request_fields = 'field'
		
		if inline_form:
			cls.form = inline_form
		
		if cls.order_data is True:
			cls.order_data = 'order'
		
		if cls.slice_data is True:
			cls.slice_data = 'offset', 'limit'
		
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
	"""
	
	__metaclass__ = BaseHandlerMeta
	
	allowed_methods = True
	"""
	Defines which HTTP methods will be allowed to run (parts of) this handler.
	Can be interpreted as a specification of which CRUD operations are
	supported. Should be an iterable of HTTP verb names (like ``('POST',
	'GET')``). Can be defined as (but not set to) ``True`` if we want its
	value to be auto-generated based on	the values of :meth:`.create`,
	:meth:`.read`, :meth:`.update` and :meth:`.delete`, which is the default
	behavior.
	"""
	
	fields = ()
	"""
	Specifies the fields that are allowed to be included in a response. It
	also serves as the set of options for request-level fields selection (see
	:attr:`request_fields`). If it is an empty iterable (the default) the
	decision whether or not a field is allowed to be included is taken by
	:meth:`.is_field_allowed`.
	
	Note that the value of this attribute is not automatically used as field
	definition on the emitter, as is the behavior of Piston's default base
	handler. See :meth:`JsonEmitter.render` for more information.
	"""
	
	request_fields = True
	"""
	Determines if request-level fields selection is enabled. Should be the
	name of the query string parameter in which the selection can be found.
	If this attribute is defined as ``True`` (which is the default) the
	default parameter name ``field`` will be used. Note that setting to (as
	opposed to "defining as") ``True`` will not work.
	
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
	
	def data(self, request, *args, **kwargs):
		data = self.data_list(request, *args, **kwargs)
		if data is None:
			data = self.data_item(request, *args, **kwargs)
		return data
	
	def data_list(self, request, *args, **kwargs):
		return None
	
	def data_item(self, request, *args, **kwargs):
		return HttpResponseGone()
	
	def get_response_data(self, request, response):
		return response.get('data')
	
	def set_response_data(self, request, response, data):
		response['data'] = data
		return response
	
	
	
	
	filter_data = {}
	order_data = None
	slice_data = None
	
	
	
	def validate(self, request, current=None):
		if forms.Form not in getattr(self.form, '__mro__', ()):
			return
		
		form = self.form(request.data)
		if not form.is_valid():
			raise FormValidationError(form)
		request.data = form.cleaned_data
	
	def do_filter_data(self, response, request, *args, **kwargs):
		return response
	
	def do_order_data(self, response, request, *args, **kwargs):
		return response
	
	def do_slice_data(self, response, request, *args, **kwargs):
		if not self.slice_data or not self.slice_data[0] in request.GET and not self.slice_data[1] in request.GET:
			return response
		
		data = response.get('data')
		start = int(request.GET.get(self.slice_data[0], 0))
		stop = start + int(request.GET.get(self.slice_data[1], 0))
		if stop == start:
			stop = None
		try:
			sliced = data[start:stop]
			# TODO: only set if not exists yet
			response['total'] = len(data)
			data = sliced
		except:
			pass
		response['data'] = data
		return response
	
	def POST(self, request, *args, **kwargs):
		self.validate(request)
		return dict(data=self.create(request, *args, **kwargs))
	
	def GET(self, request, *args, **kwargs):
		response = dict(data=self.read(request, *args, **kwargs))
		response = self.do_filter_data(response, request, *args, **kwargs)
		response = self.do_order_data(response, request, *args, **kwargs)
		response = self.do_slice_data(response, request, *args, **kwargs)
		# response = self.filter_fields(response, self.get_requested_fields(request))
		return response
	
	def PUT(self, request, *args, **kwargs):
		self.validate(request, current=self.data_item(request, *args, **kwargs))
		return dict(data=self.update(request, *args, **kwargs))
	
	def DELETE(self, request, *args, **kwargs):
		response = dict(data=self.delete(request, *args, **kwargs))
		response = self.do_filter_data(response, request, *args, **kwargs)
		response = self.do_order_data(response, request, *args, **kwargs)
		response = self.do_slice_data(response, request, *args, **kwargs)
		# response = self.filter_fields(response, self.get_requested_fields(request))
		return response
	
	def create(self, request, *args, **kwargs):
		"""
		Overridable implementation of CRUD's Create.
		"""
		return request.data
	
	def read(self, request, *args, **kwargs):
		return self.data(request, *args, **kwargs)
	
	def update(self, request, *args, **kwargs):
		return request.data
	
	def delete(self, request, *args, **kwargs):
		return self.data(request, *args, **kwargs)
	
	def post_construct(self, request, unconstructed, constructed):
		# TODO: Make this an overridable piece of logic (like the others).
		if settings.DEBUG:
			constructed['meta'] = dict(
				query_log=connection.queries,
				query_count=len(connection.queries),
			)
		return constructed


class ModelHandlerMeta(BaseHandlerMeta):
	
	def __new__(meta, name, bases, attrs):
		# TODO: Raise exception if no model type is in `attrs`.
		# TODO: Raise exception if form in `attrs` is not of type `forms.
		# ModelForm`?
		cls = super(ModelHandlerMeta, meta).__new__(meta, name, bases, attrs)
		
		# Do not override `cls.form` if it has a truthy value, regardless if
		# it is an instance of `forms.Form` or not. `cls.validate()` may be
		# overridden in order to deal with other types of forms.
		if False and not cls.form and cls.model:
			try:
				class Form(forms.ModelForm):
					class Meta:
						model = cls.model
						fields = cls.fields
						exclude = cls.exclude_save
			except FieldError:
				# TODO: Raise an exception that makes sense in the current
				# context.
				raise
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
	A list of field names that should be excluded from the field selection in
	"""
	
	exclude_save = ()
	"""
	A list of field names that 
	"""
	
	def validate(self, request, current=None):
		if forms.ModelForm not in getattr(self.form, '__mro__', ()):
			return super(ModelHandler, self).validate(request, current)
		
		form = self.form(request.data, instance=current)
		if not form.is_valid():
			raise FormValidationError(form)
		request.data = form.save(commit=False)
	
	
	def data(self, request, *args, **kwargs):
		for field, _ in kwargs.iteritems():
			if self.model._meta.get_field(field).unique:
				# We found a condition that is guaranteed to be unique
				# identifier, so we can switch to singular mode -- we won't
				# put returned data in a list for example.
				return self.data_item(request, *args, **kwargs)
		return self.data_list(request, *args, **kwargs)
	
	def data_list(self, request, *args, **kwargs):
		return self.model.objects.filter(**kwargs)
	
	def data_item(self, request, *args, **kwargs):
		return self.data_list(request, *args, **kwargs).get(**kwargs)
	
	def data_count(self, data):
		return data.count()
	
	def do_filter_data(self, response, request, *args, **kwargs):
		data = response.get('data')
		if not isinstance(data, QuerySet) or not self.filter_data:
			return response
		
		# Do away with all records that do not match the provided filter terms
		# (if any).
		for param, fields in self.filter_data.iteritems():
			query = Q()
			for term in request.GET.get(param, '').split():
				for field in fields:
					query |= Q(**{ '%s__icontains' % field: term })
			data = data.filter(query)
		response['data'] = data
		return response
	
	def do_order_data(self, response, request, *args, **kwargs):
		data = response.get('data')
		if not isinstance(data, QuerySet) or not self.order_data:
			return response
		
		# TODO: Allow for more specifically defined ordering than is enabled
		# by `order_by()`.
		response['data'] = data.order_by(*request.GET.getlist(self.order_data))
		
		return response
	
	def create(self, request, *args, **kwargs):
		request.data.save()
		return super(ModelHandler, self).create(request, *args, **kwargs)
	
	def update(self, request, *args, **kwargs):
		request.data.save()
		return super(ModelHandler, self).update(request, *args, **kwargs)
	
	def post_construct(self, request, unconstructed, constructed):
		if request.method.upper() == 'DELETE':
			unconstructed.get('data').delete()
		return super(ModelHandler, self).post_construct(request, unconstructed, constructed)



"""
class ModelHandlerMeta(BaseHandlerMeta):
	
	def __new__(meta, name, bases, attrs):
		# TODO: Raise exception if no model type is in `attrs`.
		# TODO: Raise exception if form in `attrs` is not of type `forms.
		# ModelForm`?
		if not attrs.get('form'):
			try:
				class Form(forms.ModelForm):
					class Meta:
						model = attrs.get('model')
						fields = attrs.get('fields')
						exclude = attrs.get('exclude_save')
			except FieldError:
				# TODO: Raise an exception that makes sense in the current
				# context.
				raise
			attrs['form'] = Form
		
		cls = super(ModelHandlerMeta, meta).__new__(meta, name, bases, attrs)
		return cls

class ModelHandler(BaseHandler):
	
	__metaclass__ = ModelHandlerMeta
	
	def get_emitter_fields(self, request):
		return self.get_requested_fields(request)
	
	model = None
	
	exclude_nested = ()
	
	exclude_save = ()
	
	def validate(self, request, *args, **kwargs):
		super(ModelHandler, self).validate(request, *args, **kwargs)
		instance = request.form.save(commit=False)
		return instance
	
	def request(self, request, *args, **kwargs):
		
		response = super(ModelHandler, self).request(request, *args, **kwargs)
		
		# from django.db.models import Q
		# query = Q()
		# for term in request.GET.get('filter', '').split():
		# 	query |= Q(**{ 'name__icontains': term })
		# data = data.filter(query)
		
		return response
	
	def POST(self, request, *args, **kwargs):
		
		return super(ModelHandler, self).POST(request, *args, **kwargs)


class BaseHandlerMeta(handler.HandlerMetaClass):
	
	def __new__(meta, name, bases, attrs):
		if not 'form' in attrs:
			if 'model' in attrs:
				try:
					class Form(forms.ModelForm):
						class Meta:
							model = attrs.get('model')
							fields = attrs.get('fields')
							exclude = attrs.get('exclude_save')
				except FieldError:
					# TODO: Raise an exception that makes sense in the current
					# context.
					raise
			else:
				class Form(forms.Form):
					pass
			attrs['form'] = Form
		
		auth = attrs.pop('authentication', None)
		
		cls = super(BaseHandlerMeta, meta).__new__(meta, name, bases, attrs)
		
		cls.resource = Resource(cls, auth)
		
		return cls

class BaseHandler(handler.BaseHandler):
	
	__metaclass__ = BaseHandlerMeta
	
	# TODO: These are irrelevant if they don't go along with `model`. The same
	# holds for `form`.
	fields = ()
	# TODO: I don't think this is actually necessary, yet we might want to
	# keep it to increase future compatibility.
	exclude = ()
	exclude_nested = ()
	exclude_save = ()
	
	def update_fields(self, request, fields):
		return tuple(set(fields).intersection(request.GET.getlist('field'))) or fields
	
	def is_singular(self, **conditions):
		for field, _ in conditions.iteritems():
			if self.model._meta.get_field(field).unique:
				# We found a condition that is guaranteed to be unique
				# identifier, so we can switch to singular mode -- we won't
				# put returned data in a list for example.
				return True
		return False
	
	def request(self, request, *args, **kwargs):
		method = getattr(self, request.method.upper(), None)
		if method is None:
			# TODO: This is technically not correct, as `self.allowed_methods`
			# did not lead us to this conclusion.
			return HttpResponseNotAllowed(self.allowed_methods)
		
		response = method(request, *args, **kwargs)
		
		if isinstance(response, HttpResponse):
			return response
		
		if settings.DEBUG:
			response['debug'] = dict(
				query_log=connection.queries,
				query_count=len(connection.queries),
			)
		
		return response
	
	# TODO: Can't/shouldn't we just leave out `*args` here? It would disable
	# support for unnamed arguments in `urls.py`, but using those would
	# probably just lead to confusing behavior anyway.
	def POST(self, request, *args, **kwargs):
		# If this request was issued to an URL that identifies an instance, we
		# will not proceed with creating a new instance, as the requester
		# probably did not intend to do that.
		if self.is_singular(**kwargs):
			# TODO: Use these Django classes everywhere, instead of the
			# shabby (and probably volatile) stuff in `piston.utils.rc`? Note
			# that Piston's source works around a bug in Django which might
			# still be there (and would need to be worked around ourselves if
			# we decide to no longer use Piston's responses).
			return HttpResponseNotAllowed(set(['GET', 'PUT', 'DELETE']).intersection(self.allowed_methods))
		
		form = self.form(request.data)
		if not form.is_valid():
			raise FormValidationError(form)
		request.form = form
		
		return dict(
			# TODO: Technically, `self.create(form.save(commit=False))` would
			# suffice.
			# TODO: We should deal with duplicate entries. See `piston.
			# handler.BaseHandler.create`.
			data=self.create(request, *args, **kwargs),
		)
	
	def GET(self, request, *args, **kwargs):
		# TODO: This assumption that we can simply use *all* keyword arguments
		# as filter conditions is way too harsh.
		request.queryset = self.model.objects.filter(**kwargs)
		
		response = dict(
			data=self.read(request, *args, **kwargs),
		)
		
		if not self.is_singular(**kwargs):
			response['total'] = response.get('data').count()
		
		return response


class AuthHandler(BaseHandler):
	
	authentication = SessionAuthentication()
"""