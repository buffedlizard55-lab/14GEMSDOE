"""GEMS Prize Challenge pipeline package (14GEMSDOE).

Modules
-------
dti          : distance-weighted Tversky index (official equations, transcribed verbatim)
raster       : GeoTIFF I/O and submission-format conformance gate
features     : catalogue-geometry and lineament feature builders
hide_recover : hide-and-recover training protocol (anti-leak by construction)
blocks       : spatially-blocked holdout splits
synthesize   : synthetic test-region generator for tests and demos

Every quantity computed here is re-derivable from the files in data/ and the
sources listed in research/knowledge_base.md.  No number is produced from memory.
"""

__version__ = "0.1.0"
