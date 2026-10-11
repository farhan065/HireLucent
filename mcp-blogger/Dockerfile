# The Blogger MCP server (github.com/zachsladecode/blogger-mcp-server, MIT).
# It only speaks stdio, so supergateway serves it over streamable HTTP, the
# same way the backend reaches the RAG MCP server.
FROM node:22-alpine

# Both are pinned so a rebuild always produces the same server.
ARG BLOGGER_MCP_COMMIT=c40673a3426c6a5c569545280e3591e64f1c966c
ARG SUPERGATEWAY_VERSION=4.1.0

WORKDIR /app

RUN apk add --no-cache git \
    && git clone https://github.com/zachsladecode/blogger-mcp-server.git . \
    && git checkout "$BLOGGER_MCP_COMMIT" \
    && npm ci \
    && npm run build \
    && npm install --global "supergateway@$SUPERGATEWAY_VERSION" \
    && rm -rf .git \
    # The server keeps its sign-in in /app/tokens.json. Point that at the
    # mounted secrets folder so the token survives a rebuild.
    && ln -s /secrets/blogger_tokens.json /app/tokens.json

COPY start.mjs .

EXPOSE 8002

CMD ["node", "start.mjs"]
