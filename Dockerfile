# Review site for the simulator-bias study. Static assets + serve.py ship in the image;
# the 1.7 GB SQLite is fetched from R2 into the /data volume on first boot (see entrypoint.sh).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl zstd ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY serve.py results_md.py AGENTS.md presentation.html measurement.html entrypoint.sh ./
COPY static ./static
RUN chmod +x entrypoint.sh
ENV DATA_DIR=/data PORT=8787
EXPOSE 8787
CMD ["./entrypoint.sh"]
