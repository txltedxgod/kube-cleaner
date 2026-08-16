FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY kube_cleaner ./kube_cleaner
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["kube-cleaner"]
