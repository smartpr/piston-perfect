try:
    from setuptools import setup
except ImportError:
	from distutils.core import setup

setup(
	name="piston-perfect",
	# http://www.python.org/dev/peps/pep-0386/
	# <main django_piston version>.dev<piston_perfect version for preceding django_piston version>
	version="0.2.3.dev1",
	author="Tim Molendijk",
	author_email="tim@smart.pr",
	url="http://github.com/smartpr/piston-perfect",
	packages=('piston_perfect', ),
	install_requires=(
		# Really should be required by Piston, but as that currently doesn't
		# happen we do it here instead. We are not sure about which Django
		# versions we support, but we only tested 1.3 so that is what we
		# require here.
		"Django>=1.3-beta,<=1.3",
		# We need [revision `e539a104d516`](http://bitbucket.org/jespern/
		# django-piston/src/e539a104d516/). Version `0.2.2` will fail,
		# `0.2.3rc1` would not fail if it weren't for [changeset
		# `c4b2d21db51a`](http://bitbucket.org/jespern/django-piston/
		# changeset/c4b2d21db51a) which states it breaks things -- it clearly
		# does. We expect this regression to be fixed before an official
		# release of `0.2.3rc1`, so that's what we require here. For more
		# explanation refer to `smartpr.api.emitters`.
		"django-pistoff",
		"xlwt>=0.7.2,<=0.7.2",
	),
	zip_safe=True,
)
