# Generate MRE API Documentation 

PURPOSE:

Uses Sphinx with autodoc and chalicedoc plugins to generate pretty HTML
documentation from docstrings in source/dataplaneapi/runtime/app.py and
source/controlplaneapi/runtime/app.py. Output docs will be saved to docs/source/output/.

### PRELIMINARY:
python3 must be installed.

### USAGE:
Within the **source** folder, run

```
./build_docs.sh
```

Finally, open output/index.html