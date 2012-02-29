from django.db.models import Q, Count

def in_all_filter(data, definition, values):
	""" 		
	``@param data``:		The queryset on which the filter will be applied on
		
	``@param definition``:	A string representing ``<field> + __in__all`', eg
	``memberships__list__in_all``
		
	``@param values``:      Tuple with the values that will be applied on the
	lookup filters.

	``@return``:	        Remaining queryset after the filters have been
	applied.

	Handles the ``__in_all`` lookup filter.
	Limits the ``data`` queryset to the model instances for which
	``field=value`` for every value in ``values``, where
	``field=definition[:-8]``. Basically performs a case sensitive search for
	all values in ``values``, with an ``AND`` operator in between.

	.. rubric:: Example

	Query on the ContactHandler: ``/contacts/?list=1&list=2&list=3``
		
	The filter ``list`` is defined as ``memberships_list__in_all``, so
	method :meth:`~piston_perfect.custom_filters.in_all_filter` is called,
	with ``values=[1,2,3]``. What the query asks for is: *give me all
	contacts that belong to ALL lists 1, 2 and 3.*

	So basically what we need to find is which ``Membership`` records contain a
	``list_id`` with value either 1 or 2 or 3. Then we count the
	appearances of ``Contact`` instances in this queryset. Every ``Contact`` that
	appears 3 times in the queryset, appears in all 3 lists, and therefore
	should be a part of the response.

	.. note::

		If any of the values in ``values`` is an empty string, or ``null`` then it's the only
		value we use to filter the data. Why? Well, say we performed a query to
		get all contacts which belong to lists [2, 3, and null]. This means:
		give me all contacts which belong to the list 2, list 3, and to no list
		(...which is impossible of course).
		So we just consider this as a query with poor semantics, and we return 
		only contacts that belong to no list!
	"""
    #TODO: Is this the optimal query???

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
	""" 
	``@param data``:		The queryset on which the filter will be applied on

	``@param definition``:	A string representing ``<field> + __isearch`', eg
	``recipients__isearch``

	``@param values``:      Tuple with the values that will be applied on the
	lookup filters.
	
	``@return``:	        Remaining queryset after the filters have been
	
	Handles the ``__isearch`` lookup filter, which performs case incensitive
	search for all values in ``values``, with an OR operator in between. 

	For every value in tuple ``values``, an ``iexact`` lookup filter is applied
	and a Q query is created, like: ``Q = ( `field`__iexact = value)``,
	where ``field`` is equal to ``definition[:-9]``

	All queries are applied one after the other, with an OR operator
	joining their results.

	"""

	field = definition[:-9]
	query = Q()

	for term in values:
		query |= Q(**{ ('%s__iexact' % field): term })
	return data.filter(query)

	
def in_list_filter(data, definition, values):
	"""
	``@param data``:		The queryset on which the filter will be applied on

	``@param definition``:	A string representing ``<field> + __in_list``, eg
	``emails__in_list``

	``@param values``:      Tuple with the values that will be applied on the
	lookup filters.
	
	``@return``:	        Remaining queryset after the filter has been
	applied.

	Handles the ``in_list`` lookup filter, which performs case insensitive
	search on the queryset ``data``. The search returns the subset of the
	queryset, for which every record's field ``field`` contains any of the
	values in ``values``.

	It should only be performed on fields that on Python level are represented
	by lists (say a Django JSONField).                                     
	
	.. rubric:: Example
	
	Query on the ContactHandler:
	``/contacts/?email=user1e@example1.com&email=user2@example2.com``

	The filter ``email`` is defined as ``emails__in_list``, so function
	:meth:`~piston_perfect.custom_filters.in_list_filter` is called, with values=['user1@example1.com'.
	'user2@example2.com']. What the query asks for is: *give me all contacts whose
	``emails`` field (which is a JSONField), contains any of the emails in
	``values``.*

	.. note::

		A smart way to find this is:
		(First keep in mind that a JSONField is on MySQL level, a text field)

			*	Find all the Contact instances that contain a string which is LIKE at least one of  the strings in
				``values``. This has 2 benefits:

				* Directly translated to SQL, so its fast.
				* Limits the size of the QuerySet drastically. 

			* Iterate on the queryset and find the Contact instances that contain
			  at least an entry EXACTLY as it is in the ``values`` list. This step is
			  very fast and light in terms of memory, since the size of the queryset is
			  really small.
 
	""" 
	# First I issue a much more generic query, and find the model instances
	# that *contain* any of the the values in ``values``. By ``contain`` we
	# mean, a LIKE SQL query.
	field = definition[:-9]
	query = Q()
	for term in values:
		query |= Q(**{'%s__icontains' % field: term})
	data = data.filter(query)

	# Convert all items of ``values`` to lowercase
	values = [value.lower() for value in values]
    
	exclude = []
	for instance in data:
        # Exclude from the queryset all records for which the intersection of
		# field ``field``, with the ``values`` list, is empty.

		# For every instance in ``data``, we retrieve the field ``field``,
		# which should be a list. We turn the values all in lowercase.
		value_list = getattr(instance, field)
		value_list = [value.lower() for value in value_list]
	
		if not set(value_list).intersection(set(values)):
			exclude.append(instance.id)

	return data.exclude(id__in=exclude)

# Maps custom lookups to their handler methods
filter_to_method = {
	'__in_all': in_all_filter,
	'__isearch': isearch_filter,
	'__in_list': in_list_filter,
}
