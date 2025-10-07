#!/bin/bash

# Скрипт для настройки n8n workflow для Task Reports
# Требуется: N8N_API_KEY в переменных окружения

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Настройка n8n Workflow для Task Reports${NC}"
echo ""

# Проверка API ключа
if [ -z "$N8N_API_KEY" ]; then
    echo -e "${RED}❌ Ошибка: N8N_API_KEY не установлен${NC}"
    echo ""
    echo "Получите API ключ в n8n:"
    echo "1. Откройте https://n8n.hhivp.com"
    echo "2. Settings → API"
    echo "3. Create API Key"
    echo ""
    echo "Затем запустите:"
    echo "  export N8N_API_KEY='your-api-key'"
    echo "  bash setup_n8n_webhook.sh"
    exit 1
fi

N8N_URL="https://n8n.hhivp.com/api/v1"
BOT_WEBHOOK_URL="http://telegram-bot-app:8080/webhooks/task-completed"

echo -e "${YELLOW}📋 Параметры:${NC}"
echo "  n8n URL: $N8N_URL"
echo "  Bot Webhook: $BOT_WEBHOOK_URL"
echo ""

# Получаем список существующих workflows
echo -e "${YELLOW}📥 Получаем список workflows...${NC}"
WORKFLOWS=$(curl -s -X GET "$N8N_URL/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json")

echo "$WORKFLOWS" | jq -r '.data[] | "\(.id) - \(.name)"' 2>/dev/null || echo "Workflows: $WORKFLOWS"
echo ""

# Создаём новый workflow для Task Reports
echo -e "${YELLOW}🔧 Создаём новый workflow 'Plane Task Completed → Bot'...${NC}"

WORKFLOW_JSON=$(cat <<'EOF'
{
  "name": "Plane Task Completed → Bot",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "plane-task-done",
        "responseMode": "onReceived",
        "options": {}
      },
      "id": "webhook-trigger",
      "name": "Webhook - Plane Task Done",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [250, 300],
      "webhookId": "plane-task-done"
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.event }}",
              "operation": "equals",
              "value2": "issue.activity.updated"
            },
            {
              "value1": "={{ $json.activity.field }}",
              "operation": "equals",
              "value2": "state"
            },
            {
              "value1": "={{ $json.activity.new_value }}",
              "operation": "contains",
              "value2": "Done"
            }
          ]
        }
      },
      "id": "if-task-done",
      "name": "IF Task is Done",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [450, 300]
    },
    {
      "parameters": {
        "functionCode": "// Извлекаем support_request_id из описания\nconst description = $input.item.json.issue?.description || '';\nlet supportRequestId = null;\n\nconst match = description.match(/support_request_id[=:\\s]+(\\d+)/i);\nif (match) {\n  supportRequestId = parseInt(match[1]);\n}\n\n// Формируем payload для бота\nconst payload = {\n  plane_issue_id: $input.item.json.issue.id,\n  plane_sequence_id: $input.item.json.issue.sequence_id,\n  plane_project_id: $input.item.json.issue.project_id,\n  task_title: $input.item.json.issue.name,\n  task_description: description,\n  closed_by: {\n    display_name: $input.item.json.activity.actor.display_name,\n    first_name: $input.item.json.activity.actor.first_name,\n    email: $input.item.json.activity.actor.email\n  },\n  closed_at: $input.item.json.timestamp,\n  support_request_id: supportRequestId\n};\n\nreturn { json: payload };"
      },
      "id": "function-transform",
      "name": "Transform Data",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [650, 300]
    },
    {
      "parameters": {
        "url": "http://telegram-bot-app:8080/webhooks/task-completed",
        "options": {
          "timeout": 10000
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ $json }}",
        "headerParameters": {
          "parameters": [
            {
              "name": "Content-Type",
              "value": "application/json"
            }
          ]
        }
      },
      "id": "http-to-bot",
      "name": "HTTP → Bot",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 3,
      "position": [850, 300]
    }
  ],
  "connections": {
    "Webhook - Plane Task Done": {
      "main": [[{"node": "IF Task is Done", "type": "main", "index": 0}]]
    },
    "IF Task is Done": {
      "main": [[{"node": "Transform Data", "type": "main", "index": 0}]]
    },
    "Transform Data": {
      "main": [[{"node": "HTTP → Bot", "type": "main", "index": 0}]]
    }
  },
  "settings": {}
}
EOF
)

RESPONSE=$(curl -s -X POST "$N8N_URL/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$WORKFLOW_JSON")

WORKFLOW_ID=$(echo "$RESPONSE" | jq -r '.data.id' 2>/dev/null)

if [ "$WORKFLOW_ID" != "null" ] && [ -n "$WORKFLOW_ID" ]; then
    echo -e "${GREEN}✅ Workflow создан успешно!${NC}"
    echo "  ID: $WORKFLOW_ID"
    echo ""

    # Активируем workflow
    echo -e "${YELLOW}🔄 Активируем workflow...${NC}"
    ACTIVATE=$(curl -s -X PATCH "$N8N_URL/workflows/$WORKFLOW_ID" \
      -H "X-N8N-API-KEY: $N8N_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"active": true}')

    echo -e "${GREEN}✅ Workflow активирован!${NC}"
    echo ""

    echo -e "${GREEN}🎉 Настройка завершена!${NC}"
    echo ""
    echo "Webhook URL для Plane:"
    echo "  https://n8n.hhivp.com/webhook/plane-task-done"
    echo ""
    echo "Следующие шаги:"
    echo "1. Настройте Plane webhook на этот URL"
    echo "2. Переведите тестовую задачу в Done"
    echo "3. Проверьте что админ получил уведомление в Telegram"

else
    echo -e "${RED}❌ Ошибка создания workflow${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi
