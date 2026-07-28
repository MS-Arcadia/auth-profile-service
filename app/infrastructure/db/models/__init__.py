"""SQLAlchemy models.

Deliberately empty of re-exports. Importing a model *module* is what registers its table on
`Base.metadata`, and `main.py` imports all five explicitly for exactly that reason — see the note
there. Re-exporting them here would work too, and would put the same load-bearing import somewhere
even easier to tidy away by accident.
"""
