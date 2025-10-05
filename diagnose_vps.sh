#!/bin/bash

echo "🔍 HHIVP Bot Diagnostic Script"
echo "=============================="

echo "📊 Container Status:"
docker-compose -f docker-compose.prod.yml ps

echo -e "\n🔍 Recent Bot Logs (last 20 lines):"
docker-compose -f docker-compose.prod.yml logs --tail=20 bot

echo -e "\n⚙️ Admin User IDs Configuration:"
cat .env.prod | grep ADMIN_USER_IDS

echo -e "\n🗄️ Database Connection Test:"
docker-compose -f docker-compose.prod.yml exec postgres psql -U bot_user -d telegram_bot_prod -c "SELECT COUNT(*) FROM bot_users;" 2>/dev/null || echo "❌ Database connection failed"

echo -e "\n👥 Registered Users in Database:"
docker-compose -f docker-compose.prod.yml exec postgres psql -U bot_user -d telegram_bot_prod -c "SELECT telegram_user_id, username, first_name, role FROM bot_users;" 2>/dev/null || echo "❌ Could not fetch users"

echo -e "\n📈 Recent Errors (if any):"
docker-compose -f docker-compose.prod.yml logs bot | grep ERROR | tail -5

echo -e "\n✅ Diagnostic completed!"
