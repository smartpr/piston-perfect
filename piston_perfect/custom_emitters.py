from pistoff.emitters import Emitter
import xlwt, StringIO
from django.utils.encoding import smart_unicode, force_unicode, smart_str
                    

def _to_unicode(string):
	""" Return the unicode repsesentation of string"""

	try:
		return unicode(string)
	except UnicodeDecodeError:
		# the string is a bytestring
		ascii_text = str(string).encode('string_escape')
		return unicode(ascii_text)

def to_utf8(string):
	"""Return the utf-8 encoded representation of the string """
	unic = _to_unicode(string)
	return unic.encode('utf-8')


class ExcelEmitter(Emitter):
	def render(self, request):
		data = self.construct()['data']

		wb = xlwt.Workbook(encoding='utf-8')
		stream = StringIO.StringIO()
        
		ws = wb.add_sheet("SmartPR")
		
		# Write field names on row 0
		col = 0
		for field_name in self.fields:
			ws.write(0, col, field_name.capitalize())
			col = col + 1

        # In case the ``data`` is a dictionary (eg the request was asking for a
		# single model instance), we transform it to a list
		if isinstance(data, dict):
			data = [data]

		row = 1		

		for record in data:
			# every record is a dict
			
			col = 0			
			for key in self.fields:
				value = ""
				field_value = record[key]
				
				# I merge lists or dicts to "\r\n"-separated strings
				# Why? 
				# 1. They look better (i think)
				# 2. They non-ASCII chars appear correctly
				if isinstance(field_value, list):
					if field_value:
						field_value = [to_utf8(item) for item in field_value]
    					value = "\r\n".join(field_value)
				elif isinstance(field_value, dict):
					if field_value:
						value = "\r\n".join(to_utf8(key) + ":" + to_utf8(value)  for key, value in
							field_value.items())
				else:
					value = to_utf8(record[key])

				ws.write(row, col, value )
				col = col + 1
			row = row + 1
		wb.save(stream)
		return stream.getvalue()
	# TODO
    # Works only for outputting handlers extending the ModelHandler class
	# Doesn't really work with outputing nested fields 

Emitter.register('excel', ExcelEmitter, 'application/vnd.ms-excel')
 
               
class HTMLEmitter(Emitter):
	def render(self, request):
		construct = self.construct()

		if 'data' in construct:
			# Correct response
			return construct['data']

		elif 'errors' in construct:
			# Validation was raised
			return construct['errors']

		return None			
		

Emitter.register('html', HTMLEmitter, 'text/html')
