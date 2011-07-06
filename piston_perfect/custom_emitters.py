from piston.emitters import Emitter
import xlwt, StringIO
from django.utils.encoding import smart_unicode, force_unicode, smart_str
                    

## {{{ http://code.activestate.com/recipes/466341/ (r1)
def _to_unicode(string):
	""" Return the unicode repsesentation of string"""

	try:
		return unicode(string)
	except UnicodeDecodeError:
		# the string is a bytestring
		ascii_text = str(string).encode('string_escape')
		return unicode(ascii_text)

def to_utf8(string):
	"""Return the utf-8 encode representation of the string """
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

		row = 1		
		for record in data:
			# every record is a dict
			
			col = 0			
			for key in self.fields:
				value = to_utf8(record[key])
				#if isinstance(value, list):
				#	value = [unicode(i).encode('utf-8') for i in value]
				#	value = unicode(value)
                #
				#if isinstance(value, dict):
				#	value = unicode(value)

				ws.write(row, col, value )
				col = col + 1
			row = row + 1
		wb.save(stream)
		return stream.getvalue()
	# TODO
    # Works only for outputting handlers extending the ModelHandler class
	# Non-ASCII characters JSONField fields appear encoded

Emitter.register('excel', ExcelEmitter, 'application/vnd.ms-excel')
 
