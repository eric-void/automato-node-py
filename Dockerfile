# 3.13 is the default (sauron, limited by Js2Py); golconda runs 3.11, so
# the test image can also be built with --build-arg PYTHON_VERSION=3.11.
ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AUTOMATO_STORAGE_DIR=/var/lib/automato \
    AUTOMATO_LOG_DIR=/var/log/automato

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc git iputils-ping \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 automato \
    && useradd --uid 1000 --gid automato --home-dir /var/lib/automato --no-create-home --shell /usr/sbin/nologin automato \
    && mkdir -p /etc/automato /var/lib/automato /var/log/automato

WORKDIR /opt/automato
COPY automato-core-py/requirements.txt /opt/automato/automato-core-py/requirements.txt
COPY automato-core-py/src /opt/automato/automato-core-py/src
COPY automato-node-py /opt/automato/automato-node-py

WORKDIR /opt/automato/automato-node-py
# The Js2Py fork has the same version as PyPI's Js2Py, so it must be installed
# first: otherwise pip keeps the PyPI release, which fails on Python > 3.11.
RUN pip install --no-cache-dir 'Js2Py @ git+https://github.com/a-j-albert/Js2Py.git@cc64a715727f110b79310b8031e0ade9c501d5d3' \
    && pip install --no-cache-dir -r requirements-all.txt \
    && pip install --no-cache-dir -r /opt/automato/automato-core-py/requirements.txt \
    && pip install --no-cache-dir selenium pygsheets \
    && python -c "import js2py; from PyNUTClient import PyNUT; import solaredge_modbus, telegram.ext; js2py.eval_js('1 + 1')"

ENV PYTHONPATH=/opt/automato/automato-node-py/src:/opt/automato/automato-core-py/src
USER automato:automato

ENTRYPOINT ["/opt/automato/automato-node-py/bin/automato-node.sh"]
CMD ["--config", "/etc/automato/automato.conf"]
