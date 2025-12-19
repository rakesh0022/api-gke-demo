# Stage 1: Build the Go application
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy the application source code
COPY server.go .

# Compile the Go application statically for minimal dependencies
RUN go build -o server server.go

# Stage 2: Create the final minimal image
FROM gcr.io/distroless/base-debian12

WORKDIR /app

# Copy the compiled binary from the builder stage
# IMPORTANT: Use the --chmod=+x flag to set the executable permission!
COPY --from=builder /app/server /app/server

EXPOSE 8080

CMD ["/app/server"]
