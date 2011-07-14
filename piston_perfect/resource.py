from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import connection
from django.http import Http404, HttpResponseBadRequest, HttpResponseGone, HttpResponseNotAllowed, HttpResponseNotFound
from pistoff import resource
from .utils import MethodNotAllowed
import datetime


class Resource(resource.Resource):
	"""
	Simple subclass of Piston's implementation.
	"""
	
	callmap = dict(zip(resource.Resource.callmap.keys(), ['request'] * 4))
	"""
	Route every request type to :meth:`.handlers.BaseHandler.request`.
	"""
	
	def __call__(self, request, *args, **kwargs):
		"""
		As soon as the resource is being called we can say that Piston has
		taken over. We take this moment to reset the query log, so we can read
		it later to get an overview of all the database queries that were
		incurred by Piston-based code (as opposed to stuff that happened
		before, like in unrelated middleware).
		"""
		connection.queries = []
		response = super(Resource, self).__call__(request, *args, **kwargs)

		# This is the only chance we have to interact with the HTTPResponse
		# object `response`. So far we were only dealing with data, which were
		# serialized using the selected emitter (line 194 of piston.resource)
		# and packed in an HTTPResponse object (line 207 or piston.resource).
		if 'format' in request.GET and request.GET.get('format') == 'excel':
			date = datetime.date.today()
			response['Content-Disposition'] = 'attachment; filename=Smart.pr-export-%s.xls' % \
				date				
		
		return response
	
	def error_handler(self, e, *args, **kwargs):
		"""
		If anything went wrong inside the handler, this method will try to
		construct a meaningful error response (or not if we want to hide the
		character of the problem from the user).
		"""
		
		if isinstance(e, ValidationError):
			return HttpResponseBadRequest(dict(
				type='validation',
				message="Invalid operation requested",
				errors=e.messages,
			))
		
		if isinstance(e, (NotImplementedError, ObjectDoesNotExist)):
			return HttpResponseGone()
		
		if isinstance(e, MethodNotAllowed):
			return HttpResponseNotAllowed(e.permitted_methods)
		
		if isinstance(e, Http404):
			return HttpResponseNotFound()
		
		# Else, force parent method to handle as a 500 (because the others are
		# useless).
		return super(Resource, self).error_handler(None, *args, **kwargs)
