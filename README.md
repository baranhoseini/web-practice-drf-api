# Web Practice API (Django + DRF)
A Django REST Framework backend for a small service marketplace:
customers create ads, contractors request/complete them, customers confirm completion and leave reviews, and support/admin manage tickets and roles.  
API documentation is provided via Swagger using **drf-spectacular**. Full automated tests included.

## Tech Stack
- Django
- Django REST Framework
- SimpleJWT (JWT auth)
- drf-spectacular (OpenAPI + Swagger UI)
- SQLite (default)


## Run project
```bash
python -m venv .venv
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

# API Docs (Swagger / OpenAPI)

Swagger UI:
http://127.0.0.1:8000/api/docs/

OpenAPI Schema (YAML):
http://127.0.0.1:8000/api/schema/

OpenAPI Schema (JSON):
http://127.0.0.1:8000/api/schema/?format=json


# Run Tests
`source .venv/bin/activate
python3 manage.py test -v 2`

