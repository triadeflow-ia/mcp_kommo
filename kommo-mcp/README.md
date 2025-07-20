# 🚀 kommo-mcp

Servidor MCP (Model Context Protocol) para integração inteligente com o **Kommo CRM**, desenvolvido em Python com estrutura modular, seguro e pronto para deploy no Railway.

## 📌 Visão Geral
Este projeto permite que agentes de IA (como Claude, ChatGPT com RAG ou custom agents) e plataformas como **n8n** possam **ler e manipular dados do Kommo CRM** de forma padronizada via protocolo MCP.

## 🔧 Funcionalidades Iniciais
- MCP Server completo com suporte a chamadas JSON-RPC
- Tool `kommo_list_leads` (listar últimos 10 leads do Kommo)
- Estrutura pronta para novas tools/resources
- Configuração via `.env`
- Deploy com Docker (Railway ready)

## 📁 Estrutura do Projeto
Veja descrição anterior para estrutura completa.

## ⚙️ Variáveis de Ambiente
```env
KOMMO_API_TOKEN=seu_token_de_longa_duracao
KOMMO_DOMAIN=https://seusubdominio.kommo.com
```

## 🚀 Como Usar
1. Clone o repositório
2. Adicione variáveis de ambiente
3. Faça deploy no Railway

## 📡 Exemplo de chamada
```json
POST /call_tool
{
  "tool_name": "kommo_list_leads",
  "input": {}
}
```

## 📃 Licença
MIT © 2025 – Tríadeflow 🚀
