import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from kommo_client import KommoClient
from tools import list_leads

server = Server("kommo-mcp")
server.register_tool(list_leads)

if __name__ == "__main__":
    stdio_server(server)
