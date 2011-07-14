"""
The contents of this module are modeled after the contents of :mod:`pistoff`
(save for some subtle changes in naming).
"""

# This import here is to guarantee patches to be applied before anything else
# in this module is used. This works well, but it pollutes the namespace. You
# get a circular reference, as :mod:`piston_perfect` imports itself as an
# attribute of itself. TODO: Can we find a cleaner solution?
import piston_perfect.patches
