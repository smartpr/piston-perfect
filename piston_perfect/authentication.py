from django.http import HttpResponseForbidden


class Authentication(object):
	"""
	Piston authenticator that blocks all requests with non-authenticated
	sessions.
	"""
	
	def is_authenticated(self, request):
		return request.user.is_authenticated()
	
	def challenge(self):
		return HttpResponseForbidden()
