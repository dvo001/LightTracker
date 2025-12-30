import os

# Make the package `app` also search the `pi/app` folder so imports like
# `from app.db.persistence import ...` work while the source lives under `pi/app`.
here = os.path.dirname(__file__)
pi_app_dir = os.path.normpath(os.path.join(here, '..', 'pi', 'app'))
if os.path.isdir(pi_app_dir):
    __path__.insert(0, pi_app_dir)
