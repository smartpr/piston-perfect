from django.http import HttpResponseForbidden

# TODO: Rename to ``DjangoAuthentication``.
class DjangoAuthentication(object):
	"""
	Piston authenticator that blocks all requests with non-authenticated
	sessions.
	"""
	
	def is_authenticated(self, request):
		return request.user.is_authenticated()
	
	def challenge(self):
		return HttpResponseForbidden()
