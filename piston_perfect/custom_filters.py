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
		# If a value is empty, or is 'null', then we apply None as the field
		# lookup value
		if value in ['', 'null']:
			value = None

		data = data.filter(**{field:value})
	return data


def isearch_filter(data, definition, values):
	""" Handles the '__isearch' lookup filter, which performs case incensitive
		search for all values in `values`, with an OR operator in between. 

		For every value in tuple `values`, an `iexact` lookup filter is applied
		and a Q query is created based on that:
			Q = ( `field`__iexact = value),
		where field is equal to definition[:-9]

		All queries are applied one after the other, with an OR operator
		joining their results.

		@param data:		The dataset on which the queries will be applied on
		@param definition:	A string representing <field> + '__isearch', eg
							'recipients__isearch'
		@param values:      Tuple with the values that will be applied on the
							lookup filters.

		@return:	        Remaining dataset after the filters have been
							applied.
	"""

	field = definition[:-9]
	query = Q()

	for term in values:
		query |= Q(**{ ('%s__iexact' % field): term })
	return data.filter(query)

	


# Maps custom lookups to their handler methods
filter_to_method = {
	'__in_all': in_all_filter,
	'__isearch': isearch_filter,
}
