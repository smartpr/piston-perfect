from django.core.exceptions import ValidationError
from django.db import connection
from django.http import HttpResponseBadRequest
from piston import resource


class Resource(resource.Resource):
	"""
	Simple subclass of Piston's implementation.
	"""
	
	callmap = dict(zip(*([resource.Resource.callmap.keys()] * 2)))
	"""
	Just some crazy Python fun way to say::
	
	    dict(POST='POST', GET='GET', ... )
	
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
		return super(Resource, self).__call__(request, *args, **kwargs)
	
	def error_handler(self, e, request, meth, em_format):
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
		
		return HttpResponseBadRequest(dict(
			type='unknown',
			message="Exception type %s" % type(e),
			error=unicode(e),
		))
