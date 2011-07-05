from piston.emitters import Emitter
import xlwt, StringIO
 
class ExcelEmitter(Emitter):
	def render(self, request):
		data = self.construct()['data']

		wb = xlwt.Workbook()
		stream = StringIO.StringIO()
        
		ws = wb.add_sheet("SmartPR")

		# Write field names on row 0
		col = 0
		for field_name in self.fields:
			ws.write(0, col, field_name.capitalize())
			col = col + 1

		row = 1
		
		for record in data:
			col = 0
			
			# every record is a dict
			
			for key in self.fields:
				ws.write(row, col, unicode(record[key]))
				col = col + 1
			row = row + 1
		wb.save(stream)

		return stream.getvalue()
	# TODO
	# What happens when data is not a list, but simply one?
	# What happens with non-model handlers?
	# Make file downloadle	
	# For the RecipientHandler that we care about basically, let's put the
	# fields we need in some logical order:
	# if self.handler = RecipientHandler:
	# fields = (Recipient.id, Recipient.name, ...)
	# Or even better: overwrite the read() method of the RecipientHandler. If
	# format=excel is there, then restrict fields to just the ones we need.


Emitter.register('excel', ExcelEmitter, 'application/vnd.ms-excel')
 
