FROM python:3.11-slim
WORKDIR /app

# Install the shared gradcafe_common package first (its own layer, so it
# only rebuilds when shared code actually changes, not on every web/-only
# edit). See src/common/ — this is why the build context is the module_6
# root rather than src/web/ alone: db_config.py, query_data.py, and
# clean.py are shared with worker/ instead of duplicated.
COPY src/common /tmp/common
RUN pip install --no-cache-dir /tmp/common

COPY src/web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/web/ .
EXPOSE 8080
USER 1000
CMD ["python", "run.py"]
