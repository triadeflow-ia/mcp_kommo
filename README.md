# MCP Server - Kommo CRM

Servidor MCP (Modular Command Protocol) criado pela **Tríadeflow** para integração inteligente com o Kommo CRM.

Este projeto permite o controle automatizado de dados no Kommo CRM — como leads, etapas, tarefas e notas — por meio de uma arquitetura modular, pronta para ser integrada com IA, n8n e outros sistemas.

---

## 🚀 Funcionalidades

- 🔄 Movimentação de leads por intenção  
- 🔍 Listagem de leads por etapa  
- ✍️ Criação de tarefas e notas (em breve)  
- 🌐 Integração com sistemas externos via protocolo MCP  
- 🔧 Pronto para deploy no Railway  

---

## 📂 Estrutura do Projeto

```
kommo-mcp/
├── tools/
│   └── list_leads.py
├── main.py
├── kommo_client.py
├── mcp_config.json
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

## 🛠 Como usar localmente

```bash
# Instale as dependências
pip install -r requirements.txt

# Execute o projeto
python kommo-mcp/main.py
```

---

## ☁️ Deploy recomendado

> **Railway**: você pode fazer deploy com um clique conectando esse repositório à sua conta no [https://railway.app](https://railway.app)

---

## 🧭 Roadmap

- [ ] Suporte a criação de tarefas  
- [ ] Endpoint de notas  
- [ ] Token de segurança na API  
- [ ] Documentação OpenAPI (Swagger)  

---

## 🤝 Feito por Tríadeflow

Soluções em IA, automações e eficiência para clínicas e negócios em crescimento.

**🌐 Site**: [https://triadeflow.com.br](https://triadeflow.com.br)  
**📧 E-mail**: contato@triadeflow.com.br  
**📱 WhatsApp**: [Clique para falar](https://wa.me/5585984551176)  
**📸 Instagram**: [@triadeflow](https://instagram.com/triadeflow)

---


