FROM python:3.12-slim

RUN groupadd --gid 1000 agent && \
    useradd --uid 1000 --gid agent --create-home --shell /bin/bash agent

WORKDIR /data
RUN chown agent:agent /data

USER agent

CMD ["sleep", "infinity"]
