class MethodNotAllowed(Exception):
	def __init__(self, *permitted_methods):
		self.permitted_methods = permitted_methods
