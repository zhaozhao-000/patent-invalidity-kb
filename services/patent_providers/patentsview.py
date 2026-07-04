"""PatentsView adapter.

The build script currently calls scripts/us_patent_lookup.py directly. This
module keeps a stable provider boundary for replacing or extending the lookup
source without changing case parsing code.
"""
