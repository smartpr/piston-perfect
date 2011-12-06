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
							``memberships__list__in_all``
		@param values:      Tuple with the values that will be applied on the
							lookup filters.

		@return:	        Remaining dataset after the filters have been
							applied.

		Example:
		Query on the ContactHandler:
		/contacts/?list=1&list=2&list=3
		
		The filter ``list`` is defined as``memberships_list__in_all``, so
		method ``in_all_filter`` is called, with values=[1,2,3]. What the query asks for
		is: give me all contacts that belong to all lists 1, 2 and 3.

		So basically what we need to find is which ``Membership`` records contain a
		``list_id`` with value either 1 or 2 or 3. Then we count the
		appearances of Contact instances in this queryset. Every contact that
		appears 3 times in the queryset, appears in all 3 lists.      

		Note:
		If any of the ``values`` is empty string, or `null` then it's the only
		value we use to filter the data. Why? Well, say we performed a query to
		get all contacts which belong to lists [2, 3, and null]. This means:
		give me all contacts which belong to the list 2, list 3, and to no list
		(...which is impossible of course).
		So we just consider this as a query with poor semantics, and we return 
		only contacts that belong to no list!

	"""
	#	eg. field = memberships__list__in                  
	field_in = definition[:-4]	
	#	eg. field = memberships_list
	field_exact = definition[:-8]

	# If an empty or ``null`` value is given, filter only based on None.
	for value in values:
		if value in ['', 'null']:
			return data.filter(**{field_exact:None})

	#	eg.	data.filter(memberships__contact__in=values)
	query = Q(**{field_in:values})

	return data.filter(query).\
		annotate(count=Count('id')).\
		filter(count=len(values))



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
