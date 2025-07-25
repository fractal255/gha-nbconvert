# Base image
# Debian GNU/Linux 12 (bookworm)
# /usr/bin/bash
# /usr/local/bin/python
# /usr/local/bin/pip3
# Python 3.12.11
FROM python:3.12-slim

LABEL maintainer "fractal255 <67816534+fractal255@users.noreply.github.com>"

# Create non-root user to run the action
RUN addgroup --system nbconvert && adduser --system --group nbconvert

# apt-get install
RUN apt-get update -y && \
    apt-get install --no-install-recommends -y git gosu && \
    apt-get autoclean && apt-get --purge --yes autoremove && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install python package
RUN /usr/local/bin/pip3 install --no-cache-dir nbconvert==7.16.6 pytest==8.4.1

# Entrypoint
WORKDIR /home/nbconvert
COPY executor.py /home/nbconvert/executor.py
COPY entrypoint.sh /home/nbconvert/entrypoint.sh
RUN chmod +x /home/nbconvert/entrypoint.sh \
    && chmod +x /home/nbconvert/executor.py

USER root
ENTRYPOINT ["/home/nbconvert/entrypoint.sh"]
