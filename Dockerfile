# Akamai SIEM -> Coralogix runtime image.
# Contains ONLY the prebuilt akamai-siem binary. No source, no credentials.
#
# Build (from this repository root):
#   docker build -t akamai-siem:local -f Dockerfile .
#
# The image runs as a non-root user (uid 100 / gid 101). Credentials (.edgerc
# and the Coralogix key JSON) are supplied at runtime as read-only Docker
# secrets, never baked in. State and output live on host bind mounts.
FROM alpine:3.20

RUN addgroup -S akamai && adduser -S -G akamai akamai

COPY akamai-siem-linux-amd64 /usr/local/bin/akamai-siem

RUN chmod 0755 /usr/local/bin/akamai-siem

USER akamai

ENTRYPOINT ["/usr/local/bin/akamai-siem"]