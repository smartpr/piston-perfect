from django.db.models import Q, Count

def in_all_filter(data, definition, values):
	""" Handles the '__in_all' lookup filter.
		For every value in tuple `values`, an `=` lookup filter is applied:
			filter(`field` = `value`),
		where field is equal to definition[:-8]
        
		The filters are applied one after the other,
		On database level, this is equal to len(values) queries being ANDed,
		which is exactly what we need.

		@param data:		The dataset on which the filters will be applied on
		@param definition:	A string representing <field> + '__in__all', eg
							memberships__list__in_all
		@param values:      Tuple with the values that will be applied on the
							lookup filters.

		@return:	        Remaining dataset after the filters have been
							applied.
	"""
	field = definition[:-8]
	
	for value in values:
		data = data.filter(**{field:value})
	return data

# Maps custom lookups to their handler methods
filter_to_method = {
	'__in_all': in_all_filter,
}
