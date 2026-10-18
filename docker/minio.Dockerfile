FROM golang:1.24-alpine AS build
RUN apk add --no-cache git ca-certificates
ENV CGO_ENABLED=0 GOMAXPROCS=2
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go install -v github.com/minio/minio@RELEASE.2025-10-15T17-29-55Z

FROM alpine:3.22
RUN apk add --no-cache ca-certificates
COPY --from=build /go/bin/minio /usr/local/bin/minio
EXPOSE 9000
ENTRYPOINT ["minio"]
