from django.db import connection
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
	
	def form_validation_response(self, error):
		"""
		If an handler form does not validate, this method will construct an
		error response containing details on why the validation failed. This
		information is represented in the format that was specified in the
		request (or in the default emitter format in case none was given).
		"""
		response = super(Resource, self).form_validation_response(error)
		response.content = dict(
			code='invalid',
			message="Invalid data supplied",
			errors=error.form.errors,
		)
		return response
