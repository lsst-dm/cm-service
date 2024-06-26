# Start a light linux distro with python 3.11
FROM python:3.11.9-slim-bookworm as base-image
# Install base packages
COPY scripts/install-base-packages.sh .
RUN ./install-base-packages.sh && rm ./install-base-packages.sh

FROM base-image AS install-image

# Install system packages only needed for building dependencies.
COPY scripts/install-dependency-packages.sh .
RUN ./install-dependency-packages.sh

# Create a Python virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV

# Make sure we use the virtualenv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Put the latest pip and setuptools in the virtualenv
RUN pip install --upgrade --no-cache-dir pip setuptools wheel

# Install the app's Python runtime dependencies
COPY requirements/main.txt ./requirements.txt
RUN pip install --quiet --no-cache-dir -r requirements.txt

# Install the application.
COPY . /workdir
WORKDIR /workdir
RUN pip install --no-cache-dir .

FROM base-image AS runtime-image

# Create the lsstsvc1 user
RUN groupadd --gid 1126 gu
RUN groupadd --gid 4085 rubin-users
RUN groupadd --gid 2218 lsst
RUN groupadd --gid 3967 lsstsvc1
RUN useradd lsstsvc1 --uid 17951 --no-user-group --gid gu --groups rubin-users,lsst,lsstsvc1 \
    --create-home --shell /bin/bash

# Make sure we don't write output into the layer store
VOLUME /output

# Copy the virtualenv
COPY --from=install-image /opt/venv /opt/venv

# Copy the startup script
COPY scripts/start-frontend.sh /start-frontend.sh

# Copy over configs and point there with env var
COPY examples /examples
ENV CM_CONFIGS=/examples

# Make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

# Switch to the lsstsvc1 user.
USER lsstsvc1

# Expose the port.
EXPOSE 8080

# Run the application.
CMD ["/start-frontend.sh"]
