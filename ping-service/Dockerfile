FROM python:3.13 as requirements-stage
WORKDIR /tmp
RUN pip install poetry
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes
FROM python:3.13
WORKDIR /code
COPY --from=requirements-stage /tmp/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./ping_thing /code/ping_thing
CMD ["uvicorn", "ping_thing.main:app", "--host", "0.0.0.0", "--port", "8080"]