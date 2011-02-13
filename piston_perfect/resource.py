from piston import resource


class Resource(resource.Resource):
	"""
	Simple subclass of Piston's implementation.
	"""
	
	callmap = dict(zip(
		resource.Resource.callmap.keys(),
		resource.Resource.callmap.keys(),
	))
	# callmap = dict(zip(
	# 	resource.Resource.callmap.keys(),
	# 	('request', ) * len(resource.Resource.callmap)
	# ))
	
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
