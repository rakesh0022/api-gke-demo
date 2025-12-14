FROM gcr.io/distroless/base-debian12

WORKDIR /app

COPY server .

EXPOSE 8080

CMD ["/app/server"]
