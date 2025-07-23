# MCP Server - Kommo CRM

Servidor MCP (Model Context Protocol) criado pela **Tríadeflow** para integração avançada com o Kommo CRM.

Este projeto oferece uma solução completa para automação e gerenciamento inteligente do Kommo CRM, permitindo controle total sobre leads, contatos, empresas, tarefas e muito mais através de uma arquitetura modular pronta para integração com IA, n8n e outros sistemas.

---

## 🚀 Funcionalidades

### 📊 Gestão de Vendas
- ✅ Criação e atualização de leads/negócios
- 🔄 Movimentação inteligente de leads entre etapas
- 📈 Análise avançada de performance de vendas
- 🎯 Distribuição inteligente de leads entre equipe
- 🏷️ Gestão de tags e campos customizados

### 👥 Gestão de Contatos e Empresas
- 📇 Criação e atualização de contatos
- 🏢 Gerenciamento completo de empresas
- 🔗 Vinculação automática entre entidades

### 📋 Automação e Tarefas
- ✍️ Criação de tarefas com prazos automáticos
- 📝 Sistema completo de notas e histórico
- 🤖 Criação de regras de automação complexas
- 📧 Comunicações multicanal (email, SMS, WhatsApp)

### 📊 Analytics e Inteligência
- 📈 Dashboard em tempo real
- 🔮 Análise preditiva de leads
- 📊 Relatórios de performance por período
- 🎯 Lead scoring automático
- 📈 Análise de probabilidade de conversão

### 🔧 Recursos Avançados
- 📥 Importação em massa com validação inteligente
- 🎯 Gestão de metas da equipe
- 🏭 Configuração de pipelines digitais
- 📢 Gestão de campanhas de marketing
- 🌐 Integração via webhooks

---

## 📂 Estrutura do Projeto

```bash
mcp_kommo/
├── src/
│   └── kommo_mcp_server.py       # Servidor MCP principal
├── tools/
│   ├── list_leads.py             # Ferramenta de listagem
│   └── ...                       # Outras ferramentas
├── examples/
│   └── example_usage.py          # Exemplos de uso
├── tests/
│   └── test_kommo_server.py      # Testes unitários
├── main.py                       # Ponto de entrada
├── kommo_client.py               # Cliente Kommo
├── mcp_config.json               # Configurações MCP
├── requirements.txt              # Dependências
├── Dockerfile                    # Container Docker
├── .env.example                  # Variáveis de ambiente
└── README.md                     # Este arquivo
```

---

## 🛠️ Instalação e Configuração

### 1. Clone o repositório
```bash
git clone https://github.com/triadeflow-ia/mcp_kommo.git
cd mcp_kommo
```

### 2. Configure as variáveis de ambiente:
```bash
cp .env.example .env
```
Edite o arquivo `.env` com suas credenciais:
```env
KOMMO_ACCESS_TOKEN=seu_token_aqui
KOMMO_BASE_URL=https://suaconta.kommo.com
```

### 3. Instale as dependências:
```bash
pip install -r requirements.txt
```

### 4. Execute o servidor:
```bash
python main.py
```

---

## 🔌 Como Usar

### Exemplo de Autenticação:
```json
{
  "tool": "authenticate",
  "arguments": {
    "access_token": "seu_token",
    "base_url": "https://suaconta.kommo.com"
  }
}
```

### Exemplo de Criação de Lead:
```json
{
  "tool": "create_lead",
  "arguments": {
    "name": "Nova Oportunidade",
    "price": 5000,
    "contact": {
      "name": "João Silva",
      "phone": "11999999999",
      "email": "joao@email.com"
    }
  }
}
```

### Exemplo de Análise de Vendas:
```json
{
  "tool": "analyze_sales_performance",
  "arguments": {
    "period": "this_month",
    "group_by": "user",
    "metrics": ["count", "value", "conversion"]
  }
}
```

---

## 🐳 Deploy com Docker

### Build da imagem:
```bash
docker build -t mcp-kommo .
```

### Execute o container:
```bash
docker run -p 8000:8000 --env-file .env mcp-kommo
```

---

## ☁️ Deploy no Railway

1. Clique no botão “Deploy on Railway”  
2. Configure as variáveis de ambiente  
3. Deploy automático ativado! 🚀

---

## 🔧 Ferramentas Disponíveis

### Gestão Básica
- `create_lead` - Cria novo lead  
- `update_lead` - Atualiza lead existente  
- `get_lead` - Busca detalhes de um lead  
- `search_leads` - Busca leads com filtros  
- `move_lead` - Move lead entre etapas  
- `create_contact` - Cria novo contato  
- `update_contact` - Atualiza contato  
- `create_task` - Cria nova tarefa  
- `add_note` - Adiciona nota  

### Recursos Avançados
- `analyze_sales_performance` - Análise de performance  
- `smart_lead_distribution` - Distribuição inteligente  
- `create_automation_rule` - Cria automações  
- `send_communication` - Envio multicanal  
- `bulk_import` - Importação em massa  
- `manage_team_goals` - Gestão de metas  
- `setup_digital_pipeline` - Pipelines digitais  
- `predictive_analysis` - Análise preditiva  
- `manage_campaign` - Gestão de campanhas  

---

## 🧭 Roadmap

- ✅ Suporte completo a leads, contatos e empresas  
- ✅ Sistema de tarefas e notas  
- ✅ Análises avançadas e dashboards  
- ✅ Distribuição inteligente de leads  
- ✅ Automações complexas  
- 🔜 Análise preditiva  
- 🔜 Interface web administrativa  
- 🔜 Integração com GPT-4 para insights  
- 🔜 Aplicativo mobile  
- 🔜 Documentação OpenAPI (Swagger)  

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

```bash
# Fork o projeto
# Crie sua feature branch
git checkout -b feature/AmazingFeature

# Commit suas mudanças
git commit -m 'Add some AmazingFeature'

# Push para a branch
git push origin feature/AmazingFeature
```

Abra um Pull Request 🚀

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

---

## 🏢 Feito por Tríadeflow

Soluções em IA, automações e eficiência para clínicas e negócios em crescimento.

- 🌐 Site: [triadeflow.com.br](https://triadeflow.com.br)  
- 📧 E-mail: contato@triadeflow.com.br  
- 📱 WhatsApp: Clique para falar  
- 📸 Instagram: [@triadeflow](https://instagram.com/triadeflow)  
- 💼 LinkedIn: [Tríadeflow](https://linkedin.com/company/triadeflow)  

---

## ⭐ Nos apoie!

Se este projeto foi útil para você, considere dar uma estrela ⭐ no GitHub!
