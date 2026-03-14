FROM golang:1.22-alpine AS builder
WORKDIR /app
# go.sum is optional on first build; go mod tidy generates it
COPY go.mod ./
COPY go.sum* ./
RUN go mod download
COPY . .
RUN go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /api ./cmd/api

FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY --from=builder /api .
COPY --from=builder /app/web/ ./web/
# migrations are embedded via go:embed — no runtime file copy needed
EXPOSE 8080
ENTRYPOINT ["/app/api"]
