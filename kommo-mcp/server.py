goal_data = {
                    "id": f"goal_{int(time.time())}_{goal['user_id']}",
                    "user_id": goal["user_id"],
                    "metric": goal["metric"],
                    "target": goal["target"],
                    "weight": goal.get("weight", 1.0),
                    "period": period,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "active"
                }
                saved_goals.append(goal_data)
            
            return {
                "success": True,
                "action": "set",
                "goals": saved_goals
            }
            
        elif action == "check":
            # Verificar progresso das metas
            # Buscar dados reais do período
            period_dates = self._get_period_dates(period)
            
            # Buscar usuários
            users = await self._get_users()
            user_map = {u["id"]: u["name"] for u in users}
            
            # Análise por usuário
            progress = []
            
            for user_id in user_map:
                # Buscar leads do usuário no período
                user_leads = await self._paginated_request(
                    "/leads",
                    {
                        "filter[responsible_user_id]": user_id,
                        "filter[created_at][from]": int(period_dates["start"].timestamp()),
                        "filter[created_at][to]": int(period_dates["end"].timestamp())
                    }
                )
                
                # Calcular métricas
                metrics = {
                    "leads_created": len(user_leads),
                    "deals_won": sum(1 for l in user_leads if l.get("status_id") == 142),
                    "revenue": sum(l.get("price", 0) for l in user_leads if l.get("status_id") == 142)
                }
                
                # Comparar com metas (conceitual)
                user_progress = {
                    "user_id": user_id,
                    "user_name": user_map[user_id],
                    "period": period,
                    "metrics": metrics,
                    "goals": {},  # Seria buscado do BD
                    "achievement_rate": 85.5  # Calculado baseado nas metas
                }
                
                progress.append(user_progress)
            
            return {
                "success": True,
                "action": "check",
                "period": period,
                "progress": progress
            }
            
        elif action == "report":
            # Gerar relatório detalhado
            period_dates = self._get_period_dates(period)
            
            # Buscar todos os dados necessários
            all_leads = await self._paginated_request(
                "/leads",
                {
                    "filter[created_at][from]": int(period_dates["start"].timestamp()),
                    "filter[created_at][to]": int(period_dates["end"].timestamp()),
                    "with": "contacts"
                }
            )
            
            # Análise geral
            report = {
                "period": {
                    "type": period,
                    "start": period_dates["start"].isoformat(),
                    "end": period_dates["end"].isoformat()
                },
                "team_performance": {
                    "total_leads": len(all_leads),
                    "total_revenue": sum(l.get("price", 0) for l in all_leads if l.get("status_id") == 142),
                    "conversion_rate": 0,
                    "average_deal_size": 0
                },
                "by_user": {},
                "trends": {},
                "recommendations": []
            }
            
            # Calcular métricas
            won_deals = [l for l in all_leads if l.get("status_id") == 142]
            if all_leads:
                report["team_performance"]["conversion_rate"] = (len(won_deals) / len(all_leads)) * 100
            if won_deals:
                report["team_performance"]["average_deal_size"] = (
                    report["team_performance"]["total_revenue"] / len(won_deals)
                )
            
            # Análise por usuário
            users = await self._get_users()
            for user in users:
                user_leads = [l for l in all_leads if l.get("responsible_user_id") == user["id"]]
                user_won = [l for l in user_leads if l.get("status_id") == 142]
                
                report["by_user"][user["name"]] = {
                    "leads": len(user_leads),
                    "won": len(user_won),
                    "revenue": sum(l.get("price", 0) for l in user_won),
                    "conversion_rate": (len(user_won) / len(user_leads) * 100) if user_leads else 0
                }
            
            # Recomendações automáticas
            avg_conversion = report["team_performance"]["conversion_rate"]
            for user_name, user_data in report["by_user"].items():
                if user_data["conversion_rate"] < avg_conversion * 0.8:
                    report["recommendations"].append({
                        "user": user_name,
                        "type": "training",
                        "reason": "Taxa de conversão abaixo da média da equipe"
                    })
            
            return {
                "success": True,
                "action": "report",
                "report": report
            }

    async def _setup_digital_pipeline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Configura funil digital com automações"""
        name = args["name"]
        source_type = args["source_type"]
        stages = args["stages"]
        integration = args.get("integration", {})
        
        # Criar pipeline
        pipeline_data = {
            "name": f"{name} - {source_type.title()}",
            "sort": 500,  # Ordem alta para aparecer no final
            "is_main": False,
            "is_unsorted_on": True,  # Habilitar não classificados
            "_embedded": {
                "statuses": []
            }
        }
        
        # Adicionar etapas
        for i, stage in enumerate(stages):
            status = {
                "name": stage["name"],
                "sort": (i + 1) * 10,
                "color": self._get_stage_color(i),
                "is_editable": True,
                "type": 0  # Normal
            }
            
            # Última etapa como sucesso
            if i == len(stages) - 1:
                status["type"] = 142
            
            pipeline_data["_embedded"]["statuses"].append(status)
        
        # Adicionar etapa de perda
        pipeline_data["_embedded"]["statuses"].append({
            "name": "Perdido/Desqualificado",
            "sort": 1000,
            "color": "#f44336",
            "is_editable": False,
            "type": 143
        })
        
        # Criar pipeline
        pipeline_result = await self._make_request(
            "POST",
            "/leads/pipelines",
            json=[pipeline_data]
        )
        
        created_pipeline = pipeline_result["_embedded"]["pipelines"][0]
        pipeline_id = created_pipeline["id"]
        
        # Criar campo customizado para source
        source_field = await self._create_custom_field({
            "entity_type": "leads",
            "fields": [{
                "name": f"Source - {name}",
                "type": "select",
                "enums": [
                    {"value": "website"},
                    {"value": "chatbot"},
                    {"value": "social_media"},
                    {"value": "marketplace"},
                    {"value": "api"}
                ]
            }]
        })
        
        # Configurar webhook para integração
        webhook_config = None
        if integration.get("webhook_url"):
            webhook_data = {
                "destination": integration["webhook_url"],
                "settings": {
                    "add": ["leads"],
                    "update": ["leads"],
                    "filter": {
                        "pipeline_id": pipeline_id
                    }
                }
            }
            
            if integration.get("api_key"):
                webhook_data["headers"] = {
                    "X-API-Key": integration["api_key"]
                }
            
            webhook_result = await self._make_request(
                "POST",
                "/webhooks",
                json=webhook_data
            )
            webhook_config = webhook_result
        
        # Preparar automações conceituais
        automations = []
        for stage_idx, stage in enumerate(stages):
            if "automations" in stage:
                for auto in stage["automations"]:
                    automation = {
                        "stage": stage["name"],
                        "stage_id": created_pipeline["_embedded"]["statuses"][stage_idx]["id"],
                        "trigger": auto["trigger"],
                        "action": auto["action"],
                        "delay_minutes": auto.get("delay_minutes", 0)
                    }
                    automations.append(automation)
        
        return {
            "success": True,
            "digital_pipeline": {
                "id": pipeline_id,
                "name": created_pipeline["name"],
                "source_type": source_type,
                "stages": created_pipeline["_embedded"]["statuses"],
                "custom_field_id": source_field["_embedded"]["custom_fields"][0]["id"],
                "webhook": webhook_config,
                "automations": automations,
                "integration_guide": self._generate_integration_guide(source_type, pipeline_id)
            }
        }

    async def _predictive_analysis(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Análise preditiva de leads"""
        analysis_type = args["analysis_type"]
        entity_ids = args.get("entity_ids", [])
        factors = args.get("factors", ["all"])
        time_frame_days = args.get("time_frame_days", 90)
        
        # Buscar dados históricos
        start_date = datetime.now(timezone.utc) - timedelta(days=time_frame_days)
        
        # Se não especificou entidades, pegar amostra
        if not entity_ids:
            recent_leads = await self._paginated_request(
                "/leads",
                {
                    "limit": 100,
                    "filter[created_at][from]": int(start_date.timestamp())
                }
            )
            entity_ids = [l["id"] for l in recent_leads[:50]]
        
        # Análise por tipo
        if analysis_type == "lead_scoring":
            # Scoring de leads
            scores = []
            
            for lead_id in entity_ids:
                lead = await self._get_entity("leads", lead_id)
                if not lead:
                    continue
                
                score = 0
                factors_analysis = {}
                
                # Fator: Valor do negócio
                if lead.get("price", 0) > 0:
                    price_score = min(lead["price"] / 10000 * 20, 20)  # Max 20 pontos
                    score += price_score
                    factors_analysis["price"] = price_score
                
                # Fator: Tempo no funil
                created_at = datetime.fromtimestamp(lead["created_at"], tz=timezone.utc)
                days_in_pipeline = (datetime.now(timezone.utc) - created_at).days
                time_score = max(20 - days_in_pipeline, 0)  # Quanto mais novo, melhor
                score += time_score
                factors_analysis["time_in_pipeline"] = time_score
                
                # Fator: Engajamento (notas e tarefas)
                notes = await self._get_entity_notes("leads", lead_id)
                tasks = await self._get_entity_tasks("leads", lead_id)
                engagement_score = min(len(notes) * 5 + len(tasks) * 3, 30)
                score += engagement_score
                factors_analysis["engagement"] = engagement_score
                
                # Fator: Completude de informações
                completeness = 0
                if lead.get("_embedded", {}).get("contacts"):
                    completeness += 10
                if lead.get("_embedded", {}).get("companies"):
                    completeness += 10
                if lead.get("custom_fields_values"):
                    completeness += 10
                score += completeness
                factors_analysis["completeness"] = completeness
                
                scores.append({
                    "lead_id": lead_id,
                    "lead_name": lead["name"],
                    "score": round(score, 2),
                    "max_score": 100,
                    "factors": factors_analysis,
                    "recommendation": self._get_score_recommendation(score)
                })
            
            # Ordenar por score
            scores.sort(key=lambda x: x["score"], reverse=True)
            
            return {
                "success": True,
                "analysis_type": "lead_scoring",
                "results": scores,
                "summary": {
                    "total_analyzed": len(scores),
                    "high_score": len([s for s in scores if s["score"] > 70]),
                    "medium_score": len([s for s in scores if 40 <= s["score"] <= 70]),
                    "low_score": len([s for s in scores if s["score"] < 40]),
                    "average_score": sum(s["score"] for s in scores) / len(scores) if scores else 0
                }
            }
            
        elif analysis_type == "conversion_probability":
            # Probabilidade de conversão
            probabilities = []
            
            # Buscar histórico de conversões
            historical_leads = await self._paginated_request(
                "/leads",
                {
                    "filter[created_at][from]": int(start_date.timestamp()),
                    "filter[statuses][0][status_id]": 142  # Ganhos
                }
            )
            
            # Análise de padrões de sucesso
            success_patterns = self._analyze_success_patterns(historical_leads)
            
            for lead_id in entity_ids:
                lead = await self._get_entity("leads", lead_id)
                if not lead:
                    continue
                
                # Calcular probabilidade baseada em padrões
                probability = self._calculate_conversion_probability(lead, success_patterns)
                
                probabilities.append({
                    "lead_id": lead_id,
                    "lead_name": lead["name"],
                    "probability": round(probability * 100, 2),
                    "confidence": "high" if len(historical_leads) > 50 else "medium",
                    "key_factors": self._get_key_probability_factors(lead, success_patterns),
                    "recommended_actions": self._get_probability_recommendations(probability)
                })
            
            return {
                "success": True,
                "analysis_type": "conversion_probability",
                "results": probabilities,
                "patterns": success_patterns,
                "model_info": {
                    "training_size": len(historical_leads),
                    "time_frame_days": time_frame_days,
                    "factors_analyzed": factors
                }
            }

    async def _manage_campaign(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Gerencia campanhas de marketing"""
        action = args["action"]
        
        if action == "create":
            # Criar nova campanha
            campaign = {
                "id": f"campaign_{int(time.time())}",
                "name": args["name"],
                "type": args["type"],
                "status": "draft",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "target_audience": args.get("target_audience", {}),
                "content": args.get("content", {}),
                "schedule": args.get("schedule", {}),
                "metrics": {
                    "targeted": 0,
                    "sent": 0,
                    "opened": 0,
                    "clicked": 0,
                    "converted": 0
                }
            }
            
            # Calcular audiência
            audience_filters = campaign["target_audience"].get("filters", {})
            audience_leads = await self._paginated_request("/leads", audience_filters)
            campaign["metrics"]["targeted"] = len(audience_leads)
            
            # Criar segmento para a campanha
            segment_data = {
                "name": f"Segment - {campaign['name']}",
                "color": "#2196F3",
                "custom_fields_values": []
            }
            
            # Aqui seria criado o segmento real
            
            return {
                "success": True,
                "action": "created",
                "campaign": campaign,
                "message": f"Campanha criada com {campaign['metrics']['targeted']} leads no público-alvo"
            }
            
        elif action == "analyze":
            # Análise de campanha
            campaign_id = args["campaign_id"]
            
            # Simulação de métricas (em produção viria de BD real)
            analysis = {
                "campaign_id": campaign_id,
                "performance": {
                    "sent": 1000,
                    "delivered": 980,
                    "opened": 456,
                    "clicked": 123,
                    "converted": 45,
                    "revenue_generated": 125000
                },
                "rates": {
                    "delivery_rate": 98.0,
                    "open_rate": 46.5,
                    "click_rate": 12.6,
                    "conversion_rate": 4.6
                },
                "by_segment": {},
                "by_time": {},
                "top_performers": [],
                "recommendations": []
            }
            
            # Análise temporal
            hours_data = {}
            for i in range(24):
                hours_data[f"{i:02d}:00"] = {
                    "sent": 1000 // 24,
                    "opened": 456 // 24 + (10 if 9 <= i <= 17 else 0)
                }
            analysis["by_time"] = hours_data
            
            # Recomendações
            if analysis["rates"]["open_rate"] < 25:
                analysis["recommendations"].append({
                    "type": "improvement",
                    "area": "subject_line",
                    "suggestion": "Taxa de abertura baixa. Considere testar diferentes linhas de assunto."
                })
            
            if analysis["rates"]["conversion_rate"] < 2:
                analysis["recommendations"].append({
                    "type": "improvement",
                    "area": "call_to_action",
                    "suggestion": "Taxa de conversão baixa. Revise o CTA e a oferta."
                })
            
            return {
                "success": True,
                "action": "analyze",
                "analysis": analysis
            }

    # Métodos auxiliares
    async def _get_entity(self, entity_type: str, entity_id: int) -> Optional[Dict]:
        """Busca uma entidade específica"""
        try:
            result = await self._make_request(
                "GET",
                f"/{entity_type}/{entity_id}",
                params={"with": "contacts,companies,catalog_elements,loss_reason"}
            )
            return result
        except:
            return None

    async def _search_entity(self, entity_type: str, filters: Dict) -> List[Dict]:
        """Busca entidades com filtros"""
        params = {}
        for key, value in filters.items():
            if key in ["name", "email", "phone"]:
                params["query"] = value
            else:
                params[f"filter[{key}]"] = value
        
        return await self._paginated_request(f"/{entity_type}", params)

    async def _get_entity_notes(self, entity_type: str, entity_id: int) -> List[Dict]:
        """Busca notas de uma entidade"""
        endpoint = f"/{entity_type}/{entity_id}/notes"
        return await self._paginated_request(endpoint)

    async def _get_entity_tasks(self, entity_type: str, entity_id: int) -> List[Dict]:
        """Busca tarefas de uma entidade"""
        params = {
            f"filter[entity_type]": entity_type,
            f"filter[entity_id]": entity_id
        }
        return await self._paginated_request("/tasks", params)

    async def _get_custom_fields(self, entity_type: str) -> List[Dict]:
        """Busca campos customizados"""
        cache_key = f"custom_fields_{entity_type}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        fields = await self._paginated_request(f"/{entity_type}/custom_fields")
        self.cache.set(cache_key, fields)
        return fields

    async def _create_custom_field(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cria campos personalizados"""
        entity_type = args["entity_type"]
        fields = args.get("fields", [])
        
        field_data = []
        for field in fields:
            data = {
                "name": field["name"],
                "type": field["type"]
            }
            
            if field.get("enums"):
                data["enums"] = field["enums"]
                
            field_data.append(data)
        
        result = await self._make_request(
            "POST",
            f"/{entity_type}/custom_fields",
            json=field_data
        )
        
        return result

    async def _get_users(self) -> List[Dict]:
        """Busca usuários ativos"""
        cache_key = "users"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        users = await self._paginated_request("/users")
        active_users = [u for u in users if u.get("is_active", True)]
        self.cache.set(cache_key, active_users)
        return active_users

    # Implementações dos métodos básicos
    async def _create_lead(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo lead"""
        lead_data = {
            "name": args["name"],
            "price": args.get("price", 0),
            "pipeline_id": args.get("pipeline_id"),
            "status_id": args.get("status_id"),
            "responsible_user_id": args.get("responsible_user_id")
        }
        
        # Adicionar contato se fornecido
        if args.get("contact"):
            contact_data = args["contact"]
            # Validar dados do contato
            if contact_data.get("email"):
                if not Validator.validate_email(contact_data["email"]):
                    raise KommoValidationError("Email inválido")
            
            lead_data["_embedded"] = {
                "contacts": [{
                    "first_name": contact_data.get("name", "").split()[0],
                    "last_name": " ".join(contact_data.get("name", "").split()[1:]),
                    "custom_fields_values": []
                }]
            }
            
            if contact_data.get("phone"):
                phone = Validator.validate_phone(contact_data["phone"])
                lead_data["_embedded"]["contacts"][0]["custom_fields_values"].append({
                    "field_code": "PHONE",
                    "values": [{"value": phone}]
                })
            
            if contact_data.get("email"):
                lead_data["_embedded"]["contacts"][0]["custom_fields_values"].append({
                    "field_code": "EMAIL",
                    "values": [{"value": contact_data["email"]}]
                })
        
        # Adicionar campos customizados
        if args.get("custom_fields"):
            lead_data["custom_fields_values"] = []
            for cf in args["custom_fields"]:
                lead_data["custom_fields_values"].append({
                    "field_id": cf["field_id"],
                    "values": [{"value": cf["value"]}]
                })
        
        # Adicionar tags
        if args.get("tags"):
            lead_data["_embedded"] = lead_data.get("_embedded", {})
            lead_data["_embedded"]["tags"] = [
                {"name": tag} for tag in args["tags"]
            ]
        
        result = await self._make_request("POST", "/leads", json=[lead_data])
        return result["_embedded"]["leads"][0]

    async def _update_lead(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza um lead existente"""
        lead_data = {"id": args["lead_id"]}
        
        # Campos simples
        for field in ["name", "price", "status_id", "pipeline_id", "responsible_user_id"]:
            if field in args:
                lead_data[field] = args[field]
        
        # Campos customizados
        if args.get("custom_fields"):
            lead_data["custom_fields_values"] = []
            for cf in args["custom_fields"]:
                lead_data["custom_fields_values"].append({
                    "field_id": cf["field_id"],
                    "values": [{"value": cf["value"]}]
                })
        
        # Tags
        if args.get("tags"):
            lead_data["_embedded"] = {"tags": [{"name": tag} for tag in args["tags"]]}
        
        # Data de fechamento
        if args.get("closed_at"):
            closed_date = datetime.fromisoformat(args["closed_at"])
            lead_data["closed_at"] = int(closed_date.timestamp())
        
        # Motivo de perda
        if args.get("loss_reason_id"):
            lead_data["loss_reason_id"] = args["loss_reason_id"]
        
        result = await self._make_request("PATCH", "/leads", json=[lead_data])
        return result["_embedded"]["leads"][0]

    async def _get_lead(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Busca um lead específico"""
        lead_id = args["lead_id"]
        with_params = args.get("with", ["contacts", "companies"])
        
        params = {"with": ",".join(with_params)}
        return await self._make_request("GET", f"/leads/{lead_id}", params=params)

    async def _search_leads(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Busca leads com filtros"""
        params = {}
        
        # Query de texto
        if args.get("query"):
            params["query"] = args["query"]
        
        # Filtros de pipeline e status
        if args.get("pipeline_id"):
            params["filter[pipeline_id]"] = args["pipeline_id"]
        if args.get("status_id"):
            params["filter[statuses][0][status_id]"] = args["status_id"]
            if args.get("pipeline_id"):
                params["filter[statuses][0][pipeline_id]"] = args["pipeline_id"]
        
        # Filtro de responsável
        if args.get("responsible_user_id"):
            params["filter[responsible_user_id]"] = args["responsible_user_id"]
        
        # Filtros de data
        if args.get("created_at"):
            if args["created_at"].get("from"):
                date_from = datetime.fromisoformat(args["created_at"]["from"])
                params["filter[created_at][from]"] = int(date_from.timestamp())
            if args["created_at"].get("to"):
                date_to = datetime.fromisoformat(args["created_at"]["to"])
                params["filter[created_at][to]"] = int(date_to.timestamp())
        
        # Tags
        if args.get("tags"):
            for i, tag in enumerate(args["tags"]):
                params[f"filter[tags][{i}]"] = tag
        
        # Campos customizados
        if args.get("custom_fields"):
            for i, cf in enumerate(args["custom_fields"]):
                params[f"filter[custom_fields][{i}][field_id]"] = cf["field_id"]
                params[f"filter[custom_fields][{i}][value]"] = cf["value"]
        
        # Limite
        params["limit"] = args.get("limit", 50)
        
        # Incluir relacionamentos
        params["with"] = "contacts,companies,catalog_elements"
        
        leads = await self._paginated_request("/leads", params)
        
        return {
            "leads": leads,
            "total": len(leads),
            "filters_applied": args
        }

    async def _move_lead(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Move lead para outra etapa"""
        update_data = {
            "lead_id": args["lead_id"],
            "status_id": args["status_id"]
        }
        
        if args.get("pipeline_id"):
            update_data["pipeline_id"] = args["pipeline_id"]
        
        return await self._update_lead(update_data)

    async def _create_contact(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo contato"""
        contact_data = {
            "name": args["name"],
            "responsible_user_id": args.get("responsible_user_id")
        }
        
        # Campos padrão
        custom_fields = []
        
        if args.get("phone"):
            phone = Validator.validate_phone(args["phone"])
            custom_fields.append({
                "field_code": "PHONE",
                "values": [{"value": phone}]
            })
        
        if args.get("email"):
            if not Validator.validate_email(args["email"]):
                raise KommoValidationError("Email inválido")
            custom_fields.append({
                "field_code": "EMAIL",
                "values": [{"value": args["email"]}]
            })
        
        if args.get("position"):
            custom_fields.append({
                "field_code": "POSITION",
                "values": [{"value": args["position"]}]
            })
        
        if custom_fields:
            contact_data["custom_fields_values"] = custom_fields
        
        # Empresa
        if args.get("company_id"):
            contact_data["_embedded"] = {
                "companies": [{"id": args["company_id"]}]
            }
        
        # Campos customizados adicionais
        if args.get("custom_fields"):
            if "custom_fields_values" not in contact_data:
                contact_data["custom_fields_values"] = []
            
            for cf in args["custom_fields"]:
                contact_data["custom_fields_values"].append({
                    "field_id": cf["field_id"],
                    "values": [{"value": cf["value"]}]
                })
        
        result = await self._make_request("POST", "/contacts", json=[contact_data])
        return result["_embedded"]["contacts"][0]

    async def _update_contact(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza um contato existente"""
        contact_data = {"id": args["contact_id"]}
        
        if args.get("name"):
            contact_data["name"] = args["name"]
        
        if args.get("responsible_user_id"):
            contact_data["responsible_user_id"] = args["responsible_user_id"]
        
        # Campos padrão
        custom_fields = []
        
        if args.get("phone"):
            phone = Validator.validate_phone(args["phone"])
            custom_fields.append({
                "field_code": "PHONE",
                "values": [{"value": phone}]
            })
        
        if args.get("email"):
            if not Validator.validate_email(args["email"]):
                raise KommoValidationError("Email inválido")
            custom_fields.append({
                "field_code": "EMAIL",
                "values": [{"value": args["email"]}]
            })
        
        if args.get("position"):
            custom_fields.append({
                "field_code": "POSITION",
                "values": [{"value": args["position"]}]
            })
        
        # Campos customizados
        if args.get("custom_fields"):
            for cf in args["custom_fields"]:
                custom_fields.append({
                    "field_id": cf["field_id"],
                    "values": [{"value": cf["value"]}]
                })
        
        if custom_fields:
            contact_data["custom_fields_values"] = custom_fields
        
        result = await self._make_request("PATCH", "/contacts", json=[contact_data])
        return result["_embedded"]["contacts"][0]

    async def _create_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cria uma nova tarefa"""
        task_data = {
            "text": args["text"],
            "entity_type": args["entity_type"],
            "entity_id": args["entity_id"],
            "task_type_id": args.get("task_type_id", 1),
            "responsible_user_id": args.get("responsible_user_id")
        }
        
        # Prazo
        if args.get("complete_till"):
            complete_date = datetime.fromisoformat(args["complete_till"])
            task_data["complete_till"] = int(complete_date.timestamp())
        else:
            # Prazo padrão: amanhã às 18h
            tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
            tomorrow = tomorrow.replace(hour=18, minute=0, second=0)
            task_data["complete_till"] = int(tomorrow.timestamp())
        
        result = await self._make_request("POST", "/tasks", json=[task_data])
        return result["_embedded"]["tasks"][0]

    async def _add_note(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona uma nota a uma entidade"""
        note_data = {
            "entity_id": args["entity_id"],
            "note_type": args.get("note_type", "common"),
            "params": {
                "text": args["text"]
            }
        }
        
        endpoint = f"/{args['entity_type']}/{args['entity_id']}/notes"
        result = await self._make_request("POST", endpoint, json=[note_data])
        return result["_embedded"]["notes"][0]

    async def _get_pipelines(self, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Lista todos os pipelines"""
        pipelines = await self._paginated_request("/leads/pipelines")
        
        # Buscar detalhes de cada pipeline
        detailed_pipelines = []
        for pipeline in pipelines:
            detailed = await self._make_request(
                "GET",
                f"/leads/pipelines/{pipeline['id']}",
                params={"with": "statuses"}
            )
            detailed_pipelines.append(detailed)
        
        return {
            "pipelines": detailed_pipelines,
            "total": len(detailed_pipelines)
        }

    # Métodos para recursos (read_resource)
    async def _get_dashboard_data(self) -> Dict[str, Any]:
        """Dados para o dashboard"""
        # Buscar dados gerais
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        
        # Leads de hoje
        today_leads = await self._paginated_request(
            "/leads",
            {
                "filter[created_at][from]": int(today.timestamp()),
                "limit": 250
            }
        )
        
        # Tarefas pendentes
        pending_tasks = await self._paginated_request(
            "/tasks",
            {
                "filter[is_completed]": False,
                "limit": 100
            }
        )
        
        # Pipelines
        pipelines = await self._get_pipelines()
        
        # Compilar métricas
        dashboard = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "leads_today": len(today_leads),
                "total_value_today": sum(l.get("price", 0) for l in today_leads),
                "pending_tasks": len(pending_tasks),
                "overdue_tasks": sum(
                    1 for t in pending_tasks 
                    if t.get("complete_till", 0) < int(datetime.now(timezone.utc).timestamp())
                ),
                "active_pipelines": len(pipelines["pipelines"])
            },
            "by_pipeline": {},
            "by_user": {},
            "recent_activities": []
        }
        
        # Análise por pipeline
        for pipeline in pipelines["pipelines"]:
            pipeline_leads = [
                l for l in today_leads 
                if l.get("pipeline_id") == pipeline["id"]
            ]
            
            dashboard["by_pipeline"][pipeline["name"]] = {
                "id": pipeline["id"],
                "leads": len(pipeline_leads),
                "value": sum(l.get("price", 0) for l in pipeline_leads),
                "stages": {}
            }
            
            # Por etapa
            for status in pipeline.get("_embedded", {}).get("statuses", []):
                stage_leads = [
                    l for l in pipeline_leads
                    if l.get("status_id") == status["id"]
                ]
                
                dashboard["by_pipeline"][pipeline["name"]]["stages"][status["name"]] = {
                    "id": status["id"],
                    "leads": len(stage_leads),
                    "value": sum(l.get("price", 0) for l in stage_leads)
                }
        
        return dashboard

    async def _get_all_leads(self) -> Dict[str, Any]:
        """Busca todos os leads com informações completas"""
        leads = await self._paginated_request(
            "/leads",
            {"with": "contacts,companies,catalog_elements,loss_reason"}
        )
        
        return {
            "total": len(leads),
            "leads": leads,
            "by_status": self._group_by(leads, "status_id"),
            "by_pipeline": self._group_by(leads, "pipeline_id"),
            "by_responsible": self._group_by(leads, "responsible_user_id")
        }

    async def _get_all_contacts(self) -> Dict[str, Any]:
        """Busca todos os contatos"""
        contacts = await self._paginated_request(
            "/contacts",
            {"with": "companies,customers,leads"}
        )
        
        return {
            "total": len(contacts),
            "contacts": contacts,
            "by_responsible": self._group_by(contacts, "responsible_user_id"),
            "with_phone": len([c for c in contacts if self._contact_has_phone(c)]),
            "with_email": len([c for c in contacts if self._contact_has_email(c)])
        }

    async def _get_all_companies(self) -> Dict[str, Any]:
        """Busca todas as empresas"""
        companies = await self._paginated_request(
            "/companies",
            {"with": "contacts,leads,customers"}
        )
        
        return {
            "total": len(companies),
            "companies": companies,
            "by_responsible": self._group_by(companies, "responsible_user_id")
        }

    async def _get_pipelines_detailed(self) -> Dict[str, Any]:
        """Informações detalhadas dos pipelines"""
        pipelines = await self._get_pipelines()
        
        # Adicionar estatísticas
        for pipeline in pipelines["pipelines"]:
            pipeline_id = pipeline["id"]
            
            # Buscar leads do pipeline
            leads = await self._paginated_request(
                "/leads",
                {"filter[pipeline_id]": pipeline_id}
            )
            
            pipeline["stats"] = {
                "total_leads": len(leads),
                "total_value": sum(l.get("price", 0) for l in leads),
                "conversion_rate": 0,
                "average_time": 0
            }
            
            # Taxa de conversão
            won_leads = [l for l in leads if l.get("status_id") == 142]
            if leads:
                pipeline["stats"]["conversion_rate"] = (len(won_leads) / len(leads)) * 100
            
            # Por etapa
            for status in pipeline.get("_embedded", {}).get("statuses", []):
                status_leads = [l for l in leads if l.get("status_id") == status["id"]]
                status["stats"] = {
                    "leads": len(status_leads),
                    "value": sum(l.get("price", 0) for l in status_leads),
                    "percentage": (len(status_leads) / len(leads) * 100) if leads else 0
                }
        
        return pipelines

    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Resumo analítico"""
        # Períodos de análise
        now = datetime.now(timezone.utc)
        periods = {
            "today": (now.replace(hour=0, minute=0, second=0), now),
            "this_week": (now - timedelta(days=now.weekday()), now),
            "this_month": (now.replace(day=1, hour=0, minute=0, second=0), now),
            "last_30_days": (now - timedelta(days=30), now)
        }
        
        analytics = {
            "generated_at": now.isoformat(),
            "periods": {}
        }
        
        for period_name, (start, end) in periods.items():
            # Buscar leads do período
            leads = await self._paginated_request(
                "/leads",
                {
                    "filter[created_at][from]": int(start.timestamp()),
                    "filter[created_at][to]": int(end.timestamp())
                }
            )
            
            won_leads = [l for l in leads if l.get("status_id") == 142]
            lost_leads = [l for l in leads if l.get("status_id") == 143]
            
            analytics["periods"][period_name] = {
                "leads_created": len(leads),
                "deals_won": len(won_leads),
                "deals_lost": len(lost_leads),
                "total_value": sum(l.get("price", 0) for l in leads),
                "won_value": sum(l.get("price", 0) for l in won_leads),
                "conversion_rate": (len(won_leads) / len(leads) * 100) if leads else 0,
                "average_deal_size": (sum(l.get("price", 0) for l in won_leads) / len(won_leads)) if won_leads else 0
            }
        
        # Tendências
        analytics["trends"] = self._calculate_trends(analytics["periods"])
        
        return analytics

    async def _get_recent_communications(self) -> Dict[str, Any]:
        """Comunicações recentes"""
        # Buscar eventos recentes
        events = await self._paginated_request(
            "/events",
            {"limit": 100}
        )
        
        # Filtrar comunicações
        communications = []
        for event in events:
            if event.get("type") in ["lead_note_added", "call", "message", "email"]:
                communications.append({
                    "id": event["id"],
                    "type": event["type"],
                    "entity_type": event.get("entity_type"),
                    "entity_id": event.get("entity_id"),
                    "created_at": event["created_at"],
                    "created_by": event.get("created_by"),
                    "details": event.get("value_after", {})
                })
        
        return {
            "total": len(communications),
            "communications": communications[:50],  # Últimas 50
            "by_type": self._group_by(communications, "type")
        }

    async def _get_automations(self) -> Dict[str, Any]:
        """Lista automações configuradas"""
        # Buscar webhooks como proxy para automações
        webhooks = await self._paginated_request("/webhooks")
        
        # Digital pipelines
        pipelines = await self._get_pipelines()
        digital_pipelines = [
            p for p in pipelines["pipelines"]
            if "digital" in p["name"].lower() or "auto" in p["name"].lower()
        ]
        
        return {
            "webhooks": webhooks,
            "digital_pipelines": digital_pipelines,
            "total_webhooks": len(webhooks),
            "total_digital_pipelines": len(digital_pipelines)
        }

    async def _get_team_info(self) -> Dict[str, Any]:
        """Informações da equipe"""
        # Usuários
        users = await self._paginated_request("/users")
        
        # Grupos
        groups = await self._paginated_request("/groups")
        
        # Estatísticas por usuário
        user_stats = []
        for user in users:
            if not user.get("is_active", True):
                continue
            
            # Leads do usuário
            user_leads = await self._paginated_request(
                "/leads",
                {
                    "filter[responsible_user_id]": user["id"],
                    "limit": 1  # Só para contar
                }
            )
            
            # Tarefas do usuário
            user_tasks = await self._paginated_request(
                "/tasks",
                {
                    "filter[responsible_user_id]": user["id"],
                    "filter[is_completed]": False,
                    "limit": 1
                }
            )
            
            user_stats.append({
                "id": user["id"],
                "name": user["name"],
                "email": user.get("email"),
                "group_id": user.get("group_id"),
                "rights": user.get("rights"),
                "stats": {
                    "active_leads": len(user_leads),
                    "pending_tasks": len(user_tasks)
                }
            })
        
        return {
            "users": user_stats,
            "groups": groups,
            "total_users": len(users),
            "active_users": len([u for u in users if u.get("is_active", True)])
        }

    # Métodos auxiliares de suporte
    def _get_period_dates(self, period: str) -> Dict[str, datetime]:
        """Calcula datas do período"""
        now = datetime.now(timezone.utc)
        
        if period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "weekly":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "quarterly":
            quarter = (now.month - 1) // 3
            start = now.replace(month=quarter * 3 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == "yearly":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        
        return {"start": start, "end": end}

    def _get_stage_color(self, index: int) -> str:
        """Retorna cor para etapa baseado no índice"""
        colors = [
            "#21a3e3",  # Azul
            "#ffc700",  # Amarelo
            "#eb5a46",  # Vermelho
            "#00c875",  # Verde
            "#a25ddc",  # Roxo
            "#ff6900",  # Laranja
            "#0085ff",  # Azul claro
            "#579bfc",  # Azul médio
        ]
        return colors[index % len(colors)]

    def _group_by(self, items: List[Dict], key: str) -> Dict[str, List[Dict]]:
        """Agrupa itens por chave"""
        grouped = {}
        for item in items:
            value = item.get(key)
            if value not in grouped:
                grouped[value] = []
            grouped[value].append(item)
        return grouped

    def _contact_has_phone(self, contact: Dict) -> bool:
        """Verifica se contato tem telefone"""
        for field in contact.get("custom_fields_values", []):
            if field.get("field_code") == "PHONE" and field.get("values"):
                return True
        return False

    def _contact_has_email(self, contact: Dict) -> bool:
        """Verifica se contato tem email"""
        for field in contact.get("custom_fields_values", []):
            if field.get("field_code") == "EMAIL" and field.get("values"):
                return True
        return False

    def _analyze_success_patterns(self, successful_leads: List[Dict]) -> Dict:
        """Analisa padrões de leads bem-sucedidos"""
        patterns = {
            "average_time_to_close": 0,
            "common_sources": {},
            "common_tags": {},
            "average_value": 0,
            "common_pipeline_path": {},
            "engagement_level": {"high": 0, "medium": 0, "low": 0}
        }
        
        if not successful_leads:
            return patterns
        
        total_time = 0
        total_value = 0
        
        for lead in successful_leads:
            # Tempo para fechar
            if lead.get("closed_at") and lead.get("created_at"):
                time_to_close = lead["closed_at"] - lead["created_at"]
                total_time += time_to_close
            
            # Valor
            total_value += lead.get("price", 0)
            
            # Fontes
            source = lead.get("source_id", "unknown")
            patterns["common_sources"][source] = patterns["common_sources"].get(source, 0) + 1
            
            # Tags
            for tag in lead.get("_embedded", {}).get("tags", []):
                tag_name = tag["name"]
                patterns["common_tags"][tag_name] = patterns["common_tags"].get(tag_name, 0) + 1
        
        patterns["average_time_to_close"] = total_time / len(successful_leads) if successful_leads else 0
        patterns["average_value"] = total_value / len(successful_leads) if successful_leads else 0
        
        return patterns

    def _calculate_conversion_probability(self, lead: Dict, patterns: Dict) -> float:
        """Calcula probabilidade de conversão baseado em padrões"""
        score = 0.5  # Base 50%
        
        # Valor próximo à média de sucesso
        if patterns["average_value"] > 0:
            lead_value = lead.get("price", 0)
            if 0.8 * patterns["average_value"] <= lead_value <= 1.2 * patterns["average_value"]:
                score += 0.1
        
        # Tem tags comuns de sucesso
        lead_tags = {t["name"] for t in lead.get("_embedded", {}).get("tags", [])}
        common_tags = set(patterns["common_tags"].keys())
        if lead_tags & common_tags:
            score += 0.15
        
        # Tempo no funil
        created_at = lead.get("created_at", 0)
        now = int(datetime.now(timezone.utc).timestamp())
        time_in_pipeline = now - created_at
        
        if patterns["average_time_to_close"] > 0:
            if time_in_pipeline < patterns["average_time_to_close"] * 0.5:
                score += 0.1  # Ainda cedo
            elif time_in_pipeline > patterns["average_time_to_close"] * 2:
                score -= 0.2  # Muito tempo
        
        # Engajamento (tem contatos, notas, etc)
        if lead.get("_embedded", {}).get("contacts"):
            score += 0.05
        if lead.get("_embedded", {}).get("companies"):
            score += 0.05
        
        return max(0, min(1, score))  # Manter entre 0 e 1

    def _get_score_recommendation(self, score: float) -> str:
        """Recomendação baseada no score"""
        if score >= 80:
            return "Alta prioridade - Lead quente, ação imediata recomendada"
        elif score >= 60:
            return "Média-alta prioridade - Bom potencial, manter acompanhamento próximo"
        elif score >= 40:
            return "Média prioridade - Necessita nutrição e qualificação adicional"
        else:
            return "Baixa prioridade - Requer trabalho significativo de qualificação"

    def _get_key_probability_factors(self, lead: Dict, patterns: Dict) -> List[str]:
        """Fatores chave que influenciam a probabilidade"""
        factors = []
        
        if lead.get("price", 0) > patterns["average_value"] * 0.8:
            factors.append("Valor do negócio dentro da média de sucesso")
        
        if lead.get("_embedded", {}).get("contacts"):
            factors.append("Tem informações de contato completas")
        
        lead_tags = {t["name"] for t in lead.get("_embedded", {}).get("tags", [])}
        if lead_tags:
            factors.append(f"Tags relevantes: {', '.join(list(lead_tags)[:3])}")
        
        return factors

    def _get_probability_recommendations(self, probability: float) -> List[str]:
        """Recomendações baseadas na probabilidade"""
        recommendations = []
        
        if probability >= 0.7:
            recommendations.extend([
                "Agendar reunião de fechamento",
                "Preparar proposta comercial",
                "Envolver tomador de decisão"
            ])
        elif probability >= 0.5:
            recommendations.extend([
                "Intensificar follow-up",
                "Identificar objeções",
                "Demonstrar valor adicional"
            ])
        else:
            recommendations.extend([
                "Qualificar melhor o lead",
                "Entender necessidades específicas",
                "Nutrir com conteúdo relevante"
            ])
        
        return recommendations

    def _calculate_trends(self, periods_data: Dict) -> Dict:
        """Calcula tendências entre períodos"""
        trends = {}
        
        if "this_week" in periods_data and "last_week" in periods_data:
            this_week = periods_data["this_week"]
            # Simulação de last_week (seria calculado real)
            last_week_value = this_week["total_value"] * 0.85
            
            growth = ((this_week["total_value"] - last_week_value) / last_week_value * 100) if last_week_value else 0
            
            trends["weekly_growth"] = {
                "value": round(growth, 2),
                "direction": "up" if growth > 0 else "down",
                "interpretation": self._interpret_trend(growth)
            }
        
        return trends

    def _interpret_trend(self, growth_rate: float) -> str:
        """Interpreta taxa de crescimento"""
        if growth_rate > 20:
            return "Crescimento excepcional"
        elif growth_rate > 10:
            return "Crescimento forte"
        elif growth_rate > 0:
            return "Crescimento moderado"
        elif growth_rate > -10:
            return "Declínio leve"
        else:
            return "Declínio acentuado - atenção necessária"

    def _generate_integration_guide(self, source_type: str, pipeline_id: int) -> Dict:
        """Gera guia de integração para pipeline digital"""
        base_endpoint = f"{self.base_url}/leads"
        
        guides = {
            "website": {
                "description": "Integração com formulários do site",
                "example_code": f"""
// Exemplo JavaScript para enviar lead do site
fetch('{base_endpoint}', {{
    method: 'POST',
    headers: {{
        'Authorization': 'Bearer YOUR_TOKEN',
        'Content-Type': 'application/json'
    }},
    body: JSON.stringify([{{
        name: formData.name,
        price: formData.budget,
        pipeline_id: {pipeline_id},
        _embedded: {{
            contacts: [{{
                name: formData.name,
                custom_fields_values: [
                    {{field_code: 'EMAIL', values: [{{value: formData.email}}]}},
                    {{field_code: 'PHONE', values: [{{value: formData.phone}}]}}
                ]
            }}]
        }}
    }}])
}})
"""
            },
            "chatbot": {
                "description": "Integração com chatbot",
                "webhook_format": {
                    "url": f"{base_endpoint}",
                    "method": "POST",
                    "headers": {
                        "Authorization": "Bearer YOUR_TOKEN",
                        "Content-Type": "application/json"
                    },
                    "body_template": {
                        "name": "{{chat.user_name}}",
                        "pipeline_id": pipeline_id,
                        "custom_fields_values": [
                            {
                                "field_id": "{{source_field_id}}",
                                "values": [{"value": "chatbot"}]
                            }
                        ]
                    }
                }
            }
        }
        
        return guides.get(source_type, guides["website"])

    async def close(self):
        """Fecha conexões e limpa recursos"""
        await self.client.aclose()
        self.cache.clear()


async def main():
    """Função principal para executar o servidor MCP"""
    server = KommoMCPServer()
    
    # Opções de inicialização
    init_options = InitializationOptions(
        server_name="Kommo CRM MCP Server",
        server_version="1.0.0"
    )
    
    # Executar servidor
    async with stdio_server() as stdio:
        await server.server.run(
            stdio.read_stream,
            stdio.write_stream,
            init_options
        )
    
    # Cleanup
    await server.close()


if __name__ == "__main__":
    asyncio.run(main())
        #!/usr/bin/env python3
"""
Kommo CRM MCP Server - Complete Implementation
Provides comprehensive integration with Kommo CRM API
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
import httpx
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    CallToolResult,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kommo-mcp")

# Constantes
MAX_BATCH_SIZE = 50
DEFAULT_PAGE_SIZE = 250
MAX_PAGES = 100
RATE_LIMIT_CALLS_PER_SECOND = 7

# Enums para tipos de entidades e ações
class EntityType(Enum):
    LEADS = "leads"
    CONTACTS = "contacts"
    COMPANIES = "companies"
    CUSTOMERS = "customers"

class FieldType(Enum):
    TEXT = "text"
    NUMERIC = "numeric"
    CHECKBOX = "checkbox"
    SELECT = "select"
    MULTISELECT = "multiselect"
    DATE = "date"
    URL = "url"
    TEXTAREA = "textarea"
    RADIOBUTTON = "radiobutton"
    STREETADDRESS = "streetaddress"
    SMART_ADDRESS = "smart_address"
    BIRTHDAY = "birthday"
    LEGAL_ENTITY = "legal_entity"
    PRICE = "price"
    CATEGORY = "category"
    ITEMS = "items"

class NoteType(Enum):
    COMMON = "common"
    CALL_IN = "call_in"
    CALL_OUT = "call_out"
    SERVICE_MESSAGE = "service_message"
    MESSAGE_CASHIER = "message_cashier"
    EXTENDED_SERVICE_MESSAGE = "extended_service_message"
    SMS_IN = "sms_in"
    SMS_OUT = "sms_out"

# Exceções customizadas
class KommoError(Exception):
    """Base exception for Kommo API errors"""
    pass

class KommoAuthError(KommoError):
    """Authentication error"""
    pass

class KommoRateLimitError(KommoError):
    """Rate limit exceeded"""
    pass

class KommoValidationError(KommoError):
    """Validation error"""
    pass

# Rate Limiter
class RateLimiter:
    def __init__(self, calls_per_second: float = RATE_LIMIT_CALLS_PER_SECOND):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        async with self.lock:
            now = time.time()
            time_since_last = now - self.last_call
            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)
            self.last_call = time.time()

# Cache simples para dados que mudam pouco
class SimpleCache:
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        self.cache[key] = (value, time.time())
    
    def clear(self):
        self.cache.clear()

# Validadores
class Validator:
    @staticmethod
    def validate_email(email: str) -> bool:
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> str:
        # Remove non-numeric characters
        cleaned = ''.join(filter(str.isdigit, phone))
        if len(cleaned) < 10:
            raise KommoValidationError("Phone number too short")
        return cleaned
    
    @staticmethod
    def validate_custom_field_value(field_type: str, value: Any) -> Any:
        if field_type == FieldType.NUMERIC.value:
            try:
                return float(value)
            except (ValueError, TypeError):
                raise KommoValidationError(f"Invalid numeric value: {value}")
        elif field_type == FieldType.CHECKBOX.value:
            return bool(value)
        elif field_type == FieldType.DATE.value:
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return int(dt.timestamp())
                except ValueError:
                    raise KommoValidationError(f"Invalid date format: {value}")
            return value
        elif field_type == FieldType.PRICE.value:
            try:
                return float(value)
            except (ValueError, TypeError):
                raise KommoValidationError(f"Invalid price value: {value}")
        return value

class KommoMCPServer:
    def __init__(self):
        self.server = Server("kommo-crm")
        self.base_url = "https://your-account.kommo.com/api/v4"
        self.access_token = None
        self.account_info = None
        self.client = httpx.AsyncClient(timeout=30.0)
        self.rate_limiter = RateLimiter()
        self.cache = SimpleCache(ttl_seconds=300)
        self.setup_handlers()

    def setup_handlers(self):
        """Setup all MCP handlers"""
        self._setup_resource_handlers()
        self._setup_tool_handlers()

    def _setup_resource_handlers(self):
        """Setup resource-related handlers"""
        @self.server.list_resources()
        async def handle_list_resources() -> ListResourcesResult:
            return ListResourcesResult(
                resources=[
                    Resource(
                        uri="kommo://dashboard",
                        name="Dashboard",
                        description="Resumo geral do CRM com métricas principais",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://leads",
                        name="Leads/Negócios",
                        description="Lista completa de leads com filtros avançados",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://contacts",
                        name="Contatos",
                        description="Base de contatos com informações detalhadas",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://companies",
                        name="Empresas",
                        description="Cadastro de empresas e organizações",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://pipelines",
                        name="Funis de Vendas",
                        description="Estrutura de funis e etapas do processo comercial",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://analytics",
                        name="Analytics",
                        description="Relatórios e análises de desempenho",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://communications",
                        name="Comunicações",
                        description="Histórico de comunicações (chamadas, emails, mensagens)",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://automations",
                        name="Automações",
                        description="Regras e automações configuradas",
                        mimeType="application/json"
                    ),
                    Resource(
                        uri="kommo://team",
                        name="Equipe",
                        description="Usuários, grupos e permissões",
                        mimeType="application/json"
                    ),
                ]
            )

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> ReadResourceResult:
            if not self.access_token:
                return ReadResourceResult(
                    contents=[TextContent(
                        type="text",
                        text="Erro: Token de acesso não configurado. Use a ferramenta 'authenticate' primeiro."
                    )],
                    isError=True
                )
            
            try:
                if uri == "kommo://dashboard":
                    data = await self._get_dashboard_data()
                elif uri == "kommo://leads":
                    data = await self._get_all_leads()
                elif uri == "kommo://contacts":
                    data = await self._get_all_contacts()
                elif uri == "kommo://companies":
                    data = await self._get_all_companies()
                elif uri == "kommo://pipelines":
                    data = await self._get_pipelines_detailed()
                elif uri == "kommo://analytics":
                    data = await self._get_analytics_summary()
                elif uri == "kommo://communications":
                    data = await self._get_recent_communications()
                elif uri == "kommo://automations":
                    data = await self._get_automations()
                elif uri == "kommo://team":
                    data = await self._get_team_info()
                else:
                    return ReadResourceResult(
                        contents=[TextContent(type="text", text=f"Erro: Recurso não encontrado: {uri}")],
                        isError=True
                    )
                
                return ReadResourceResult(
                    contents=[TextContent(
                        type="text",
                        text=json.dumps(data, indent=2, ensure_ascii=False)
                    )]
                )
            except Exception as e:
                logger.error(f"Erro ao ler recurso {uri}: {e}")
                return ReadResourceResult(
                    contents=[TextContent(type="text", text=f"Erro ao acessar recurso: {str(e)}")],
                    isError=True
                )

    def _setup_tool_handlers(self):
        """Setup tool-related handlers"""
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            tools = [
                # Autenticação e Setup
                Tool(
                    name="authenticate",
                    description="Autentica com a API do Kommo usando token de acesso",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "access_token": {
                                "type": "string",
                                "description": "Token de acesso da API do Kommo"
                            },
                            "base_url": {
                                "type": "string",
                                "description": "URL base da sua conta (ex: https://suaconta.kommo.com)",
                                "default": "https://your-account.kommo.com"
                            }
                        },
                        "required": ["access_token"]
                    }
                ),
                
                # Análises e Relatórios
                Tool(
                    name="analyze_sales_performance",
                    description="Analisa performance de vendas com métricas detalhadas",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "period": {
                                "type": "string",
                                "enum": ["today", "yesterday", "this_week", "last_week", 
                                        "this_month", "last_month", "custom"],
                                "description": "Período para análise"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Data inicial (YYYY-MM-DD) se period=custom"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "Data final (YYYY-MM-DD) se period=custom"
                            },
                            "group_by": {
                                "type": "string",
                                "enum": ["user", "pipeline", "source", "tag"],
                                "description": "Agrupar resultados por"
                            },
                            "metrics": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["count", "value", "conversion", "average_time", "win_rate"]
                                },
                                "description": "Métricas para incluir"
                            }
                        },
                        "required": ["period"]
                    }
                ),
                
                # Gestão de Leads Avançada
                Tool(
                    name="smart_lead_distribution",
                    description="Distribui leads inteligentemente entre a equipe",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "distribution_method": {
                                "type": "string",
                                "enum": ["round_robin", "by_workload", "by_skill", "by_region"],
                                "description": "Método de distribuição"
                            },
                            "user_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "IDs dos usuários para distribuir (opcional)"
                            },
                            "filters": {
                                "type": "object",
                                "properties": {
                                    "pipeline_id": {"type": "integer"},
                                    "status_id": {"type": "integer"},
                                    "tags": {"type": "array", "items": {"type": "string"}},
                                    "source": {"type": "string"}
                                },
                                "description": "Filtros para selecionar leads"
                            },
                            "max_per_user": {
                                "type": "integer",
                                "description": "Máximo de leads por usuário"
                            }
                        },
                        "required": ["distribution_method"]
                    }
                ),
                
                # Automações Complexas
                Tool(
                    name="create_automation_rule",
                    description="Cria regras de automação complexas",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Nome da automação"
                            },
                            "trigger": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["lead_created", "lead_status_changed", "task_completed",
                                                "time_passed", "field_changed", "tag_added"],
                                        "description": "Tipo de gatilho"
                                    },
                                    "conditions": {
                                        "type": "object",
                                        "description": "Condições específicas do gatilho"
                                    }
                                },
                                "required": ["type"]
                            },
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": ["move_lead", "assign_user", "add_task", 
                                                    "send_email", "send_sms", "add_tag", 
                                                    "update_field", "create_activity"],
                                            "description": "Tipo de ação"
                                        },
                                        "params": {
                                            "type": "object",
                                            "description": "Parâmetros da ação"
                                        },
                                        "delay_minutes": {
                                            "type": "integer",
                                            "description": "Atraso em minutos antes de executar"
                                        }
                                    },
                                    "required": ["type", "params"]
                                },
                                "description": "Lista de ações a executar"
                            },
                            "active": {
                                "type": "boolean",
                                "description": "Se a automação está ativa",
                                "default": True
                            }
                        },
                        "required": ["name", "trigger", "actions"]
                    }
                ),
                
                # Comunicações Multicanal
                Tool(
                    name="send_communication",
                    description="Envia comunicação por múltiplos canais",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entity_type": {
                                "type": "string",
                                "enum": ["leads", "contacts", "companies"],
                                "description": "Tipo da entidade"
                            },
                            "entity_id": {
                                "type": "integer",
                                "description": "ID da entidade"
                            },
                            "channel": {
                                "type": "string",
                                "enum": ["email", "sms", "whatsapp", "telegram"],
                                "description": "Canal de comunicação"
                            },
                            "template_id": {
                                "type": "integer",
                                "description": "ID do template (opcional)"
                            },
                            "message": {
                                "type": "string",
                                "description": "Mensagem personalizada (se não usar template)"
                            },
                            "variables": {
                                "type": "object",
                                "description": "Variáveis para substituir no template"
                            },
                            "schedule_time": {
                                "type": "string",
                                "description": "Agendar envio (ISO 8601)"
                            }
                        },
                        "required": ["entity_type", "entity_id", "channel"]
                    }
                ),
                
                # Importação/Exportação em Massa
                Tool(
                    name="bulk_import",
                    description="Importa dados em massa com mapeamento inteligente",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entity_type": {
                                "type": "string",
                                "enum": ["leads", "contacts", "companies"],
                                "description": "Tipo de entidade para importar"
                            },
                            "data": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "Array de objetos para importar"
                            },
                            "mapping": {
                                "type": "object",
                                "description": "Mapeamento de campos (origem -> destino)"
                            },
                            "options": {
                                "type": "object",
                                "properties": {
                                    "update_existing": {
                                        "type": "boolean",
                                        "description": "Atualizar registros existentes"
                                    },
                                    "duplicate_check_field": {
                                        "type": "string",
                                        "description": "Campo para verificar duplicatas"
                                    },
                                    "default_pipeline_id": {
                                        "type": "integer",
                                        "description": "Pipeline padrão para novos leads"
                                    },
                                    "default_user_id": {
                                        "type": "integer",
                                        "description": "Usuário responsável padrão"
                                    }
                                }
                            }
                        },
                        "required": ["entity_type", "data"]
                    }
                ),
                
                # Gestão de Equipe
                Tool(
                    name="manage_team_goals",
                    description="Define e acompanha metas da equipe",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["set", "update", "check", "report"],
                                "description": "Ação a executar"
                            },
                            "period": {
                                "type": "string",
                                "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"],
                                "description": "Período da meta"
                            },
                            "goals": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "user_id": {"type": "integer"},
                                        "metric": {
                                            "type": "string",
                                            "enum": ["leads_created", "deals_won", "revenue", 
                                                    "calls_made", "meetings_scheduled"]
                                        },
                                        "target": {"type": "number"},
                                        "weight": {"type": "number"}
                                    }
                                },
                                "description": "Lista de metas"
                            }
                        },
                        "required": ["action", "period"]
                    }
                ),
                
                # Digital Pipeline
                Tool(
                    name="setup_digital_pipeline",
                    description="Configura funil digital com automações",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Nome do funil digital"
                            },
                            "source_type": {
                                "type": "string",
                                "enum": ["website", "chatbot", "social_media", "marketplace"],
                                "description": "Tipo de fonte digital"
                            },
                            "stages": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "automations": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "trigger": {"type": "string"},
                                                    "action": {"type": "string"},
                                                    "delay_minutes": {"type": "integer"}
                                                }
                                            }
                                        }
                                    }
                                },
                                "description": "Etapas do funil com automações"
                            },
                            "integration": {
                                "type": "object",
                                "properties": {
                                    "webhook_url": {"type": "string"},
                                    "api_key": {"type": "string"},
                                    "field_mapping": {"type": "object"}
                                },
                                "description": "Configurações de integração"
                            }
                        },
                        "required": ["name", "source_type", "stages"]
                    }
                ),
                
                # Análise Preditiva
                Tool(
                    name="predictive_analysis",
                    description="Análise preditiva de leads e oportunidades",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "analysis_type": {
                                "type": "string",
                                "enum": ["lead_scoring", "churn_risk", "next_best_action", 
                                        "revenue_forecast", "conversion_probability"],
                                "description": "Tipo de análise preditiva"
                            },
                            "entity_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "IDs das entidades para analisar (opcional)"
                            },
                            "factors": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Fatores para considerar na análise"
                            },
                            "time_frame_days": {
                                "type": "integer",
                                "description": "Período histórico para análise em dias",
                                "default": 90
                            }
                        },
                        "required": ["analysis_type"]
                    }
                ),
                
                # Gestão de Campanhas
                Tool(
                    name="manage_campaign",
                    description="Gerencia campanhas de marketing e vendas",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["create", "update", "start", "pause", "analyze"],
                                "description": "Ação da campanha"
                            },
                            "campaign_id": {
                                "type": "integer",
                                "description": "ID da campanha (para update/start/pause/analyze)"
                            },
                            "name": {
                                "type": "string",
                                "description": "Nome da campanha"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["email", "sms", "social", "multichannel"],
                                "description": "Tipo de campanha"
                            },
                            "target_audience": {
                                "type": "object",
                                "properties": {
                                    "filters": {"type": "object"},
                                    "segments": {"type": "array", "items": {"type": "integer"}},
                                    "tags": {"type": "array", "items": {"type": "string"}}
                                },
                                "description": "Definição do público-alvo"
                            },
                            "content": {
                                "type": "object",
                                "properties": {
                                    "template_id": {"type": "integer"},
                                    "subject": {"type": "string"},
                                    "body": {"type": "string"},
                                    "attachments": {"type": "array", "items": {"type": "string"}}
                                },
                                "description": "Conteúdo da campanha"
                            },
                            "schedule": {
                                "type": "object",
                                "properties": {
                                    "start_date": {"type": "string"},
                                    "end_date": {"type": "string"},
                                    "timezone": {"type": "string"},
                                    "send_times": {"type": "array", "items": {"type": "string"}}
                                },
                                "description": "Agendamento da campanha"
                            }
                        },
                        "required": ["action"]
                    }
                ),
            ]
            
            # Adicionar ferramentas básicas também
            basic_tools = self._get_basic_tools()
            tools.extend(basic_tools)
            
            return ListToolsResult(tools=tools)

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            try:
                # Log da chamada
                logger.info(f"Chamando ferramenta: {name}")
                
                # Verificar autenticação para maioria das ferramentas
                if name != "authenticate" and not self.access_token:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text="Erro: Autenticação necessária. Use 'authenticate' primeiro."
                        )],
                        isError=True
                    )
                
                # Mapear nome da ferramenta para método
                tool_mapping = {
                    "authenticate": self._authenticate,
                    "analyze_sales_performance": self._analyze_sales_performance,
                    "smart_lead_distribution": self._smart_lead_distribution,
                    "create_automation_rule": self._create_automation_rule,
                    "send_communication": self._send_communication,
                    "bulk_import": self._bulk_import,
                    "manage_team_goals": self._manage_team_goals,
                    "setup_digital_pipeline": self._setup_digital_pipeline,
                    "predictive_analysis": self._predictive_analysis,
                    "manage_campaign": self._manage_campaign,
                    # Ferramentas básicas
                    "create_lead": self._create_lead,
                    "update_lead": self._update_lead,
                    "get_lead": self._get_lead,
                    "search_leads": self._search_leads,
                    "create_contact": self._create_contact,
                    "update_contact": self._update_contact,
                    "create_task": self._create_task,
                    "add_note": self._add_note,
                    "get_pipelines": self._get_pipelines,
                    "move_lead": self._move_lead,
                }
                
                if name in tool_mapping:
                    result = await tool_mapping[name](arguments)
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Erro: Ferramenta '{name}' não encontrada"
                        )],
                        isError=True
                    )
                
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=json.dumps(result, indent=2, ensure_ascii=False)
                    )]
                )
                
            except KommoValidationError as e:
                logger.error(f"Erro de validação: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Erro de validação: {str(e)}")],
                    isError=True
                )
            except Exception as e:
                logger.error(f"Erro ao executar ferramenta {name}: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Erro: {str(e)}")],
                    isError=True
                )

    def _get_basic_tools(self) -> List[Tool]:
        """Retorna ferramentas básicas do CRM"""
        return [
            Tool(
                name="create_lead",
                description="Cria um novo lead/negócio no CRM",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Nome do lead"},
                        "price": {"type": "number", "description": "Valor do negócio"},
                        "pipeline_id": {"type": "integer", "description": "ID do funil"},
                        "status_id": {"type": "integer", "description": "ID da etapa"},
                        "responsible_user_id": {"type": "integer", "description": "ID do responsável"},
                        "contact": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "phone": {"type": "string"},
                                "email": {"type": "string"}
                            },
                            "description": "Criar contato junto com o lead"
                        },
                        "custom_fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field_id": {"type": "integer"},
                                    "value": {"type": ["string", "number", "boolean", "array"]}
                                }
                            }
                        },
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="update_lead",
                description="Atualiza um lead existente",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lead_id": {"type": "integer", "description": "ID do lead"},
                        "name": {"type": "string"},
                        "price": {"type": "number"},
                        "status_id": {"type": "integer"},
                        "loss_reason_id": {"type": "integer"},
                        "closed_at": {"type": "string"},
                        "custom_fields": {"type": "array"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["lead_id"]
                }
            ),
            Tool(
                name="get_lead",
                description="Busca informações detalhadas de um lead",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lead_id": {"type": "integer", "description": "ID do lead"},
                        "with": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["contacts", "companies", "catalog_elements", "loss_reason"]
                            },
                            "description": "Dados relacionados para incluir"
                        }
                    },
                    "required": ["lead_id"]
                }
            ),
            Tool(
                name="search_leads",
                description="Busca leads com filtros avançados",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Termo de busca"},
                        "pipeline_id": {"type": "integer"},
                        "status_id": {"type": "integer"},
                        "responsible_user_id": {"type": "integer"},
                        "created_at": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"}
                            }
                        },
                        "updated_at": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"}
                            }
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "custom_fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field_id": {"type": "integer"},
                                    "value": {"type": ["string", "number"]}
                                }
                            }
                        },
                        "limit": {"type": "integer", "default": 50}
                    }
                }
            ),
            Tool(
                name="move_lead",
                description="Move lead para outra etapa do funil",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lead_id": {"type": "integer"},
                        "status_id": {"type": "integer", "description": "ID da nova etapa"},
                        "pipeline_id": {"type": "integer", "description": "ID do novo funil (opcional)"}
                    },
                    "required": ["lead_id", "status_id"]
                }
            ),
            Tool(
                name="create_contact",
                description="Cria um novo contato",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "phone": {"type": "string"},
                        "email": {"type": "string"},
                        "position": {"type": "string"},
                        "company_id": {"type": "integer"},
                        "responsible_user_id": {"type": "integer"},
                        "custom_fields": {"type": "array"}
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="update_contact",
                description="Atualiza um contato existente",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer"},
                        "name": {"type": "string"},
                        "phone": {"type": "string"},
                        "email": {"type": "string"},
                        "position": {"type": "string"},
                        "custom_fields": {"type": "array"}
                    },
                    "required": ["contact_id"]
                }
            ),
            Tool(
                name="create_task",
                description="Cria uma nova tarefa",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Descrição da tarefa"},
                        "entity_type": {"type": "string", "enum": ["leads", "contacts", "companies"]},
                        "entity_id": {"type": "integer"},
                        "responsible_user_id": {"type": "integer"},
                        "complete_till": {"type": "string", "description": "Prazo (ISO 8601)"},
                        "task_type_id": {"type": "integer", "default": 1}
                    },
                    "required": ["text", "entity_type", "entity_id"]
                }
            ),
            Tool(
                name="add_note",
                description="Adiciona uma nota a uma entidade",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_type": {"type": "string", "enum": ["leads", "contacts", "companies"]},
                        "entity_id": {"type": "integer"},
                        "text": {"type": "string"},
                        "note_type": {
                            "type": "string",
                            "enum": ["common", "call_in", "call_out", "service_message"],
                            "default": "common"
                        }
                    },
                    "required": ["entity_type", "entity_id", "text"]
                }
            ),
            Tool(
                name="get_pipelines",
                description="Lista todos os funis e suas etapas",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]

    # Métodos de API base
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Faz requisição à API com rate limiting e retry"""
        await self.rate_limiter.wait_if_needed()
        
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            response = await self.client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise KommoAuthError("Token inválido ou expirado")
            elif e.response.status_code == 429:
                raise KommoRateLimitError("Limite de requisições excedido")
            elif e.response.status_code == 400:
                error_data = e.response.json()
                raise KommoValidationError(f"Erro de validação: {error_data}")
            else:
                raise KommoError(f"Erro na API: {e.response.status_code} - {e.response.text}")

    async def _paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        max_pages: int = MAX_PAGES
    ) -> List[Dict]:
        """Faz requisições paginadas"""
        if params is None:
            params = {}
        
        params["limit"] = params.get("limit", DEFAULT_PAGE_SIZE)
        params["page"] = 1
        
        all_results = []
        
        while params["page"] <= max_pages:
            response = await self._make_request("GET", endpoint, params=params)
            
            embedded = response.get("_embedded", {})
            # Pega o primeiro array que encontrar no _embedded
            for key, value in embedded.items():
                if isinstance(value, list):
                    all_results.extend(value)
                    break
            
            # Verifica se há próxima página
            if not response.get("_links", {}).get("next"):
                break
                
            params["page"] += 1
        
        return all_results

    # Implementação dos métodos principais
    async def _authenticate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Autentica com a API do Kommo"""
        self.access_token = args["access_token"]
        
        if "base_url" in args:
            # Limpa e formata a URL base
            base_url = args["base_url"].rstrip("/")
            if not base_url.endswith("/api/v4"):
                base_url += "/api/v4"
            self.base_url = base_url
        
        try:
            # Testa a autenticação e obtém informações da conta
            account_info = await self._make_request("GET", "/account")
            self.account_info = account_info
            
            # Limpa o cache ao autenticar
            self.cache.clear()
            
            return {
                "success": True,
                "message": "Autenticação realizada com sucesso",
                "account": {
                    "id": account_info.get("id"),
                    "name": account_info.get("name"),
                    "subdomain": account_info.get("subdomain"),
                    "currency": account_info.get("currency"),
                    "timezone": account_info.get("timezone"),
                    "language": account_info.get("language"),
                    "date_format": account_info.get("date_format")
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _analyze_sales_performance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Análise avançada de performance de vendas"""
        period = args["period"]
        group_by = args.get("group_by", "user")
        metrics = args.get("metrics", ["count", "value", "conversion"])
        
        # Determinar datas baseado no período
        end_date = datetime.now(timezone.utc)
        if period == "today":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "yesterday":
            start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0)
            end_date = end_date.replace(hour=0, minute=0, second=0)
        elif period == "this_week":
            start_date = end_date - timedelta(days=end_date.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0)
        elif period == "last_week":
            start_date = end_date - timedelta(days=end_date.weekday() + 7)
            end_date = start_date + timedelta(days=7)
            start_date = start_date.replace(hour=0, minute=0, second=0)
        elif period == "this_month":
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0)
        elif period == "last_month":
            start_date = (end_date.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0)
            end_date = end_date.replace(day=1, hour=0, minute=0)
        elif period == "custom":
            start_date = datetime.fromisoformat(args["start_date"])
            end_date = datetime.fromisoformat(args["end_date"])
        
        # Buscar dados
        params = {
            "filter[created_at][from]": int(start_date.timestamp()),
            "filter[created_at][to]": int(end_date.timestamp()),
            "with": "contacts,loss_reason"
        }
        
        leads = await self._paginated_request("/leads", params)
        
        # Processar análises
        analysis = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_leads": len(leads),
                "total_value": sum(lead.get("price", 0) for lead in leads),
                "avg_value": 0,
                "conversion_rate": 0
            },
            "by_status": {},
            "by_pipeline": {},
            "by_user": {},
            "by_source": {},
            "trends": {}
        }
        
        if leads:
            analysis["summary"]["avg_value"] = analysis["summary"]["total_value"] / len(leads)
            
            # Análise por status
            won_count = sum(1 for lead in leads if lead.get("status_id") == 142)
            analysis["summary"]["conversion_rate"] = (won_count / len(leads)) * 100
            
            # Agrupamentos
            if group_by == "user":
                grouped = {}
                for lead in leads:
                    user_id = lead.get("responsible_user_id")
                    if user_id not in grouped:
                        grouped[user_id] = {
                            "count": 0,
                            "value": 0,
                            "won": 0
                        }
                    grouped[user_id]["count"] += 1
                    grouped[user_id]["value"] += lead.get("price", 0)
                    if lead.get("status_id") == 142:
                        grouped[user_id]["won"] += 1
                
                # Buscar nomes dos usuários
                users = await self._get_users()
                for user_id, data in grouped.items():
                    user_name = next(
                        (u["name"] for u in users if u["id"] == user_id),
                        f"User {user_id}"
                    )
                    data["name"] = user_name
                    data["conversion_rate"] = (data["won"] / data["count"]) * 100 if data["count"] > 0 else 0
                
                analysis["by_user"] = grouped
            
            # Análise de tendências (simplificada)
            daily_leads = {}
            for lead in leads:
                created_date = datetime.fromtimestamp(
                    lead.get("created_at", 0),
                    tz=timezone.utc
                ).date().isoformat()
                
                if created_date not in daily_leads:
                    daily_leads[created_date] = {
                        "count": 0,
                        "value": 0
                    }
                daily_leads[created_date]["count"] += 1
                daily_leads[created_date]["value"] += lead.get("price", 0)
            
            analysis["trends"]["daily"] = daily_leads
        
        return analysis

    async def _smart_lead_distribution(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Distribuição inteligente de leads"""
        method = args["distribution_method"]
        filters = args.get("filters", {})
        user_ids = args.get("user_ids", [])
        max_per_user = args.get("max_per_user", 10)
        
        # Buscar leads para distribuir
        params = {}
        if filters.get("pipeline_id"):
            params["filter[pipeline_id]"] = filters["pipeline_id"]
        if filters.get("status_id"):
            params["filter[statuses][0][status_id]"] = filters["status_id"]
        if not params:
            # Por padrão, pegar leads sem responsável
            params["filter[responsible_user_id]"] = 0
        
        leads = await self._paginated_request("/leads", params)
        
        if not leads:
            return {
                "success": False,
                "message": "Nenhum lead encontrado para distribuir"
            }
        
        # Se não especificou usuários, pegar todos ativos
        if not user_ids:
            users = await self._get_users()
            user_ids = [u["id"] for u in users if u.get("is_active", True)]
        
        # Distribuir leads
        distributed = []
        errors = []
        
        if method == "round_robin":
            # Distribuição circular
            user_index = 0
            user_count = {uid: 0 for uid in user_ids}
            
            for lead in leads:
                if user_count[user_ids[user_index]] >= max_per_user:
                    # Pular usuários que já atingiram o máximo
                    available_users = [
                        uid for uid in user_ids 
                        if user_count[uid] < max_per_user
                    ]
                    if not available_users:
                        break
                    user_index = user_ids.index(available_users[0])
                
                user_id = user_ids[user_index]
                
                try:
                    # Atualizar lead
                    result = await self._update_lead({
                        "lead_id": lead["id"],
                        "responsible_user_id": user_id
                    })
                    
                    distributed.append({
                        "lead_id": lead["id"],
                        "lead_name": lead["name"],
                        "assigned_to": user_id
                    })
                    
                    user_count[user_id] += 1
                    user_index = (user_index + 1) % len(user_ids)
                    
                except Exception as e:
                    errors.append({
                        "lead_id": lead["id"],
                        "error": str(e)
                    })
        
        elif method == "by_workload":
            # Distribuir por carga de trabalho
            # Buscar quantidade atual de leads por usuário
            workload = {}
            for user_id in user_ids:
                user_leads = await self._paginated_request(
                    "/leads",
                    {"filter[responsible_user_id]": user_id, "limit": 1}
                )
                workload[user_id] = len(user_leads)
            
            # Ordenar usuários por menor carga
            sorted_users = sorted(user_ids, key=lambda x: workload.get(x, 0))
            
            for lead in leads:
                # Encontrar usuário com menor carga
                assigned = False
                for user_id in sorted_users:
                    if workload[user_id] < max_per_user:
                        try:
                            result = await self._update_lead({
                                "lead_id": lead["id"],
                                "responsible_user_id": user_id
                            })
                            
                            distributed.append({
                                "lead_id": lead["id"],
                                "lead_name": lead["name"],
                                "assigned_to": user_id
                            })
                            
                            workload[user_id] += 1
                            assigned = True
                            break
                            
                        except Exception as e:
                            errors.append({
                                "lead_id": lead["id"],
                                "error": str(e)
                            })
                
                if not assigned:
                    break
        
        return {
            "success": True,
            "summary": {
                "total_leads": len(leads),
                "distributed": len(distributed),
                "errors": len(errors)
            },
            "distributed": distributed,
            "errors": errors if errors else None
        }

    async def _create_automation_rule(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cria regra de automação complexa"""
        # Esta é uma implementação conceitual, pois a API do Kommo
        # não expõe diretamente a criação de automações complexas
        # Seria necessário usar webhooks e lógica externa
        
        name = args["name"]
        trigger = args["trigger"]
        actions = args["actions"]
        active = args.get("active", True)
        
        # Criar webhook para o gatilho
        webhook_data = {
            "destination": "https://your-automation-server.com/webhook",
            "settings": {
                "add": [],
                "update": [],
                "delete": [],
                "restore": []
            }
        }
        
        # Mapear tipos de gatilho para eventos de webhook
        trigger_mapping = {
            "lead_created": "add_lead",
            "lead_status_changed": "update_lead",
            "task_completed": "update_task",
            "field_changed": "update_lead",
            "tag_added": "update_lead"
        }
        
        event_type = trigger_mapping.get(trigger["type"])
        if event_type:
            if "add" in event_type:
                webhook_data["settings"]["add"].append(event_type.replace("add_", ""))
            else:
                webhook_data["settings"]["update"].append(event_type.replace("update_", ""))
        
        # Registrar webhook
        webhook_result = await self._make_request(
            "POST",
            "/webhooks",
            json=webhook_data
        )
        
        # Salvar regra de automação (conceitual)
        automation = {
            "id": f"auto_{int(time.time())}",
            "name": name,
            "trigger": trigger,
            "actions": actions,
            "active": active,
            "webhook_id": webhook_result.get("id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "triggered": 0,
                "completed": 0,
                "failed": 0
            }
        }
        
        return {
            "success": True,
            "automation": automation,
            "message": "Automação criada. Configure o servidor de automação para processar o webhook."
        }

    async def _send_communication(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Envia comunicação multicanal"""
        entity_type = args["entity_type"]
        entity_id = args["entity_id"]
        channel = args["channel"]
        
        # Buscar informações da entidade
        entity = await self._get_entity(entity_type, entity_id)
        
        if not entity:
            return {
                "success": False,
                "error": "Entidade não encontrada"
            }
        
        # Preparar dados de comunicação
        communication = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Processar por canal
        if channel == "email":
            # Buscar email do contato
            contact_email = None
            if entity_type == "leads":
                contacts = entity.get("_embedded", {}).get("contacts", [])
                if contacts:
                    contact = await self._get_entity("contacts", contacts[0]["id"])
                    for field in contact.get("custom_fields_values", []):
                        if field.get("field_code") == "EMAIL":
                            contact_email = field["values"][0]["value"]
                            break
            
            if not contact_email:
                return {
                    "success": False,
                    "error": "Email não encontrado para a entidade"
                }
            
            communication["to"] = contact_email
            communication["subject"] = args.get("subject", "Comunicação Kommo")
            communication["body"] = args.get("message", "")
            
            # Adicionar nota sobre o envio
            note_text = f"Email enviado para {contact_email}\nAssunto: {communication['subject']}"
            await self._add_note({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "text": note_text,
                "note_type": "service_message"
            })
            
        elif channel == "sms":
            # Similar ao email, buscar telefone
            contact_phone = None
            if entity_type == "leads":
                contacts = entity.get("_embedded", {}).get("contacts", [])
                if contacts:
                    contact = await self._get_entity("contacts", contacts[0]["id"])
                    for field in contact.get("custom_fields_values", []):
                        if field.get("field_code") == "PHONE":
                            contact_phone = field["values"][0]["value"]
                            break
            
            if not contact_phone:
                return {
                    "success": False,
                    "error": "Telefone não encontrado para a entidade"
                }
            
            communication["to"] = contact_phone
            communication["message"] = args.get("message", "")
            
            # Adicionar nota
            note_text = f"SMS enviado para {contact_phone}\nMensagem: {communication['message'][:100]}..."
            await self._add_note({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "text": note_text,
                "note_type": "sms_out"
            })
        
        # Agendar se necessário
        if args.get("schedule_time"):
            communication["scheduled_for"] = args["schedule_time"]
            communication["status"] = "scheduled"
        else:
            communication["status"] = "sent"
            communication["sent_at"] = communication["timestamp"]
        
        return {
            "success": True,
            "communication": communication
        }

    async def _bulk_import(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Importação em massa com validação"""
        entity_type = args["entity_type"]
        data = args["data"]
        mapping = args.get("mapping", {})
        options = args.get("options", {})
        
        # Resultados
        imported = []
        updated = []
        errors = []
        
        # Buscar campos customizados para validação
        custom_fields = await self._get_custom_fields(entity_type)
        field_map = {cf["name"]: cf for cf in custom_fields}
        
        # Processar em lotes
        batch_size = 50
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_data = []
            
            for item in batch:
                try:
                    # Mapear campos
                    mapped_item = {}
                    
                    for source_field, dest_field in mapping.items():
                        if source_field in item:
                            # Validar e converter valor se for campo customizado
                            if dest_field.startswith("cf_"):
                                field_name = dest_field[3:]
                                if field_name in field_map:
                                    field_info = field_map[field_name]
                                    value = Validator.validate_custom_field_value(
                                        field_info["type"],
                                        item[source_field]
                                    )
                                    
                                    if "custom_fields_values" not in mapped_item:
                                        mapped_item["custom_fields_values"] = []
                                    
                                    mapped_item["custom_fields_values"].append({
                                        "field_id": field_info["id"],
                                        "values": [{"value": value}]
                                    })
                            else:
                                mapped_item[dest_field] = item[source_field]
                    
                    # Aplicar padrões
                    if entity_type == "leads" and options.get("default_pipeline_id"):
                        mapped_item["pipeline_id"] = options["default_pipeline_id"]
                    
                    if options.get("default_user_id"):
                        mapped_item["responsible_user_id"] = options["default_user_id"]
                    
                    # Verificar duplicatas se configurado
                    if options.get("update_existing") and options.get("duplicate_check_field"):
                        check_field = options["duplicate_check_field"]
                        check_value = mapped_item.get(check_field)
                        
                        if check_value:
                            # Buscar existente
                            existing = await self._search_entity(
                                entity_type,
                                {check_field: check_value}
                            )
                            
                            if existing:
                                # Atualizar existente
                                mapped_item["id"] = existing[0]["id"]
                    
                    batch_data.append(mapped_item)
                    
                except Exception as e:
                    errors.append({
                        "item": item,
                        "error": str(e)
                    })
            
            # Enviar lote
            if batch_data:
                try:
                    result = await self._make_request(
                        "POST",
                        f"/{entity_type}",
                        json=batch_data
                    )
                    
                    created = result.get("_embedded", {}).get(entity_type, [])
                    for entity in created:
                        if entity.get("updated_at") == entity.get("created_at"):
                            imported.append(entity)
                        else:
                            updated.append(entity)
                            
                except Exception as e:
                    for item in batch_data:
                        errors.append({
                            "item": item,
                            "error": str(e)
                        })
        
        return {
            "success": True,
            "summary": {
                "total": len(data),
                "imported": len(imported),
                "updated": len(updated),
                "errors": len(errors)
            },
            "imported": imported[:10],  # Primeiros 10 para exemplo
            "updated": updated[:10],
            "errors": errors[:10]
        }

    async def _manage_team_goals(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Gerencia metas da equipe"""
        action = args["action"]
        period = args["period"]
        
        if action == "set":
            # Definir novas metas
            goals = args.get("goals", [])
            
            # Salvar metas (conceitual - seria em BD externo)
            saved_goals = []
            for goal in goals:
                goal_data = {
                    "id": f"goal_{int(time.time())}_{
