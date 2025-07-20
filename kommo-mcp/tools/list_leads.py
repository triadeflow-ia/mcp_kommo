from mcp.types import Tool, CallToolResult
from kommo_client import KommoClient

def call_tool(input: dict) -> CallToolResult:
    client = KommoClient()
    leads_data = client.get_leads()
    leads = [{"id": l["id"], "name": l["name"]} for l in leads_data["_embedded"]["leads"]]
    return CallToolResult(output={"leads": leads})

list_leads = Tool(
    name="kommo_list_leads",
    description="Lista os 10 últimos leads do Kommo CRM",
    inputSchema={},  # <-- CORRETO
    outputSchema={   # <-- CORRETO
        "leads": [
            {"id": "ID do lead", "name": "Nome do lead"}
        ]
    },
    call=call_tool
)

