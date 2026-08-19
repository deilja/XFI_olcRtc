FROM golang:1.26-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN go install github.com/magefile/mage@latest

WORKDIR /src
RUN git clone --recurse-submodules https://github.com/openlibrecommunity/olcrtc.git .
RUN /go/bin/mage build

FROM debian:bookworm-slim
RUN useradd --system --create-home --uid 10001 olcrtc
WORKDIR /opt/olcrtc
COPY --from=builder /src/build/olcrtc-linux-amd64 /opt/olcrtc/olcrtc-linux-amd64
RUN chmod +x /opt/olcrtc/olcrtc-linux-amd64 && mkdir -p /opt/olcrtc/data && chown -R olcrtc:olcrtc /opt/olcrtc
USER olcrtc
ENTRYPOINT ["/opt/olcrtc/olcrtc-linux-amd64"]
